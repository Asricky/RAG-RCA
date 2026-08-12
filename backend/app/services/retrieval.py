import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

from ..config import settings


class RetrievalUnavailable(RuntimeError):
    pass


class HybridSearchBackend(Protocol):
    def hybrid_search(
        self,
        query: str,
        filters: dict,
        top_k: int,
        alpha: float,
        selected_ids: set[str],
    ) -> tuple[list[dict], int]: ...


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def retrieve(search_backend: HybridSearchBackend, question: str, ui_context: dict, config: dict) -> dict:
    """Retrieve evidence through OpenSearch BM25 + Sentence Transformer kNN fusion."""
    started = time.perf_counter()
    alpha = max(0.0, min(1.0, float(config.get("alpha", settings.default_alpha))))
    top_k = max(1, min(100, int(config.get("top_k", settings.default_top_k))))
    before = max(0, int(config.get("time_before_minutes", 5)))
    after = max(0, int(config.get("time_after_minutes", 5)))
    selected_ids = set(ui_context.get("selected_log_ids") or [])
    anchor = _parse(ui_context.get("incident_timestamp"))
    time_from, time_to = _parse(ui_context.get("time_from")), _parse(ui_context.get("time_to"))
    if anchor and not time_from:
        time_from, time_to = anchor - timedelta(minutes=before), anchor + timedelta(minutes=after)

    selected_nodes = sorted(set(ui_context.get("selected_nodes") or []))
    context_text = " ".join(
        part for part in (
            question,
            " ".join(selected_nodes),
            ui_context.get("trace_id") or "",
            ui_context.get("session_id") or "",
            ui_context.get("keyword") or "",
        ) if part
    )
    filters = {
        "nodes": selected_nodes,
        "severities": sorted(set(ui_context.get("severity") or [])),
        "trace_id": ui_context.get("trace_id"),
        "session_id": ui_context.get("session_id"),
        "time_from": time_from.isoformat() if time_from else None,
        "time_to": time_to.isoformat() if time_to else None,
    }

    ranked, candidate_count = search_backend.hybrid_search(
        query=context_text,
        filters=filters,
        top_k=top_k,
        alpha=alpha,
        selected_ids=selected_ids,
    )
    evidence: list[dict] = []
    seen_messages: set[tuple[str, str]] = set()
    for item in ranked:
        dedupe_key = (str(item.get("node", "")), str(item.get("message", "")))
        if dedupe_key in seen_messages:
            continue
        seen_messages.add(dedupe_key)
        evidence.append(item)
        if len(evidence) >= top_k:
            break
    for index, item in enumerate(evidence, 1):
        item["evidence_id"] = f"E{index}"
        item["rank"] = index

    ordered_context = "\n".join(
        f"[{item['evidence_id']}] {item['@timestamp']} | {item['node']} | {item['severity']} | {item['message']}"
        for item in sorted(evidence, key=lambda row: row["@timestamp"])
    )
    elapsed = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "incident_id": ui_context.get("incident_id"),
        "retrieval_config": {
            "alpha": alpha,
            "top_k": top_k,
            "time_before_minutes": before,
            "time_after_minutes": after,
            "embedding_model": settings.embedding_model,
            "backend": "opensearch_bm25_sentence_transformer_knn",
        },
        "candidate_count": candidate_count,
        "evidence_logs": evidence,
        "ordered_context": ordered_context,
        "retrieval_latency_ms": elapsed,
    }
