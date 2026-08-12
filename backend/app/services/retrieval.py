import hashlib
import math
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..config import settings


TOKEN_RE = re.compile(r"[a-zA-Z0-9_-]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def embed_text(text: str, dimension: int = 384) -> list[float]:
    """Deterministic feature-hashing encoder used as the offline semantic fallback."""
    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[index] += sign * (1.0 + min(len(token), 12) / 12)
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _cosine(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second))


def _normalise(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [1.0 if high > 0 else 0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def retrieve(logs: list[dict], question: str, ui_context: dict, config: dict) -> dict:
    started = time.perf_counter()
    alpha = max(0.0, min(1.0, float(config.get("alpha", settings.default_alpha))))
    top_k = int(config.get("top_k", settings.default_top_k))
    before = int(config.get("time_before_minutes", 5))
    after = int(config.get("time_after_minutes", 5))
    selected_ids = set(ui_context.get("selected_log_ids") or [])
    selected_nodes = set(ui_context.get("selected_nodes") or [])
    severities = set(ui_context.get("severity") or [])
    trace_id, session_id = ui_context.get("trace_id"), ui_context.get("session_id")
    time_from, time_to = _parse(ui_context.get("time_from")), _parse(ui_context.get("time_to"))
    anchor = _parse(ui_context.get("incident_timestamp"))
    if anchor and not time_from:
        time_from, time_to = anchor - timedelta(minutes=before), anchor + timedelta(minutes=after)

    candidates: list[dict] = []
    for log in logs:
        stamp = _parse(log["@timestamp"])
        if time_from and stamp < time_from or time_to and stamp > time_to:
            continue
        if selected_nodes and log.get("node") not in selected_nodes:
            continue
        if severities and log.get("severity") not in severities:
            continue
        if trace_id and log.get("trace_id") != trace_id:
            continue
        if session_id and log.get("session_id") != session_id:
            continue
        candidates.append(log)
    if selected_ids:
        selected = [item for item in logs if item["log_id"] in selected_ids]
        seen = {item["log_id"] for item in candidates}
        candidates = selected + [item for item in candidates if item["log_id"] not in {row["log_id"] for row in selected}]
    if not candidates:
        candidates = logs[:50]

    context_terms = " ".join([question, " ".join(selected_nodes), trace_id or "", session_id or "", ui_context.get("keyword") or ""])
    query_terms = tokenize(context_terms)
    documents = [tokenize(item.get("search_text", item["message"])) for item in candidates]
    document_count = max(1, len(documents))
    avg_length = sum(map(len, documents)) / document_count or 1
    df = Counter(term for terms in documents for term in set(terms))
    bm25_scores: list[float] = []
    for terms in documents:
        frequency = Counter(terms)
        score = 0.0
        for term in query_terms:
            count = frequency[term]
            if not count:
                continue
            inverse = math.log(1 + (document_count - df[term] + 0.5) / (df[term] + 0.5))
            denom = count + 1.5 * (1 - 0.75 + 0.75 * len(terms) / avg_length)
            score += inverse * count * 2.5 / denom
        bm25_scores.append(score)
    query_vector = embed_text(context_terms, settings.embedding_dimension)
    semantic_scores = [_cosine(query_vector, embed_text(" ".join(terms), settings.embedding_dimension)) for terms in documents]
    normal_bm25, normal_semantic = _normalise(bm25_scores), _normalise(semantic_scores)
    ranked = []
    for index, log in enumerate(candidates):
        boost = 0.12 if log["log_id"] in selected_ids else 0.0
        final = min(1.0, alpha * normal_bm25[index] + (1 - alpha) * normal_semantic[index] + boost)
        ranked.append({**log, "bm25_score": round(normal_bm25[index], 4), "semantic_score": round(normal_semantic[index], 4), "final_score": round(final, 4)})
    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    evidence = []
    seen_messages: set[tuple] = set()
    for item in ranked:
        dedupe_key = (item["node"], item["message"])
        if dedupe_key in seen_messages:
            continue
        seen_messages.add(dedupe_key)
        evidence.append(item)
        if len(evidence) >= top_k:
            break
    for index, item in enumerate(evidence, 1):
        item["evidence_id"] = f"E{index}"
        item["rank"] = index
    ordered = sorted(evidence, key=lambda item: item["@timestamp"])
    ordered_context = "\n".join(
        f"[{item['evidence_id']}] {item['@timestamp']} | {item['node']} | {item['severity']} | {item['message']}" for item in ordered
    )
    elapsed = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "incident_id": ui_context.get("incident_id"),
        "retrieval_config": {"alpha": alpha, "top_k": top_k, "time_before_minutes": before, "time_after_minutes": after, "embedding_model": settings.embedding_model},
        "candidate_count": len(candidates), "evidence_logs": evidence, "ordered_context": ordered_context, "retrieval_latency_ms": elapsed,
    }

