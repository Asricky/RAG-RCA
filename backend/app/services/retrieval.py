import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

from ..config import settings
from .domain_mapping import domain_mapping


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


class KnowledgeSearchBackend(Protocol):
    def search(self, query: str, *, interfaces: list[str], components: list[str], error_codes: list[str], limit: int | None = None) -> list[dict]: ...


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def retrieve(
    search_backend: HybridSearchBackend,
    question: str,
    ui_context: dict,
    config: dict,
    knowledge_backend: KnowledgeSearchBackend | None = None,
) -> dict:
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

    kpi_context = ui_context.get("kpi_context") or {}
    enrichment = domain_mapping.enrich(
        kpi_context.get("kpi_name"),
        kpi_level=kpi_context.get("kpi_level"),
        related_interfaces=kpi_context.get("related_interfaces") or ui_context.get("related_interfaces"),
        related_components=kpi_context.get("related_components") or ui_context.get("related_components"),
    )
    if kpi_context:
        kpi_context = {**kpi_context, **enrichment}
    selected_nodes = sorted(set(ui_context.get("selected_nodes") or []))
    related_interfaces = sorted(set(kpi_context.get("related_interfaces") or ui_context.get("related_interfaces") or []))
    related_components = sorted(set(kpi_context.get("related_components") or ui_context.get("related_components") or []))
    context_text = " ".join(
        part for part in (
            question,
            " ".join(selected_nodes),
            str(kpi_context.get("kpi_name") or ""),
            str(kpi_context.get("node") or ""),
            " ".join(related_interfaces),
            " ".join(related_components),
            ui_context.get("trace_id") or "",
            ui_context.get("session_id") or "",
            ui_context.get("error_code") or "",
            ui_context.get("keyword") or "",
        ) if part
    )
    filters = {
        "nodes": selected_nodes,
        "components": related_components,
        "interfaces": related_interfaces,
        "dataset_id": ui_context.get("dataset_id"),
        "severities": sorted(set(ui_context.get("severity") or [])),
        "trace_id": ui_context.get("trace_id"),
        "session_id": ui_context.get("session_id"),
        "error_code": ui_context.get("error_code"),
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
    # Context engineering keeps genuine operational failures ahead of synthetic
    # transient noise while retaining BM25/kNN scores for inspection.
    ranked.sort(
        key=lambda item: (
            bool(item.get("error_code")) and not str(item.get("error_code")).endswith("_TRANSIENT"),
            str(item.get("severity") or "").upper() in {"ERROR", "CRITICAL"},
            float(item.get("final_score") or 0.0),
            str(item.get("@timestamp") or ""),
        ),
        reverse=True,
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
        item["evidence_id"] = f"L{index}"
        item["type"] = "LOG"
        item["rank"] = index

    error_codes = sorted({
        str(item.get("error_code"))
        for item in evidence
        if item.get("error_code") and not str(item.get("error_code")).endswith("_TRANSIENT")
    })
    knowledge_evidence = []
    if evidence and knowledge_backend:
        knowledge_query = " ".join([
            question,
            " ".join(related_interfaces),
            " ".join(related_components),
            " ".join(error_codes),
            " ".join(str(item.get("message") or "") for item in evidence[:5]),
        ])
        for index, item in enumerate(knowledge_backend.search(
            knowledge_query,
            interfaces=related_interfaces,
            components=related_components,
            error_codes=error_codes,
            limit=settings.knowledge_top_k,
        ), 1):
            knowledge_evidence.append({**item, "evidence_id": f"R{index}", "type": "KNOWLEDGE"})

    kpi_evidence = []
    if kpi_context and kpi_context.get("current_value") is not None:
        kpi_evidence.append({
            "evidence_id": "K1",
            "type": "KPI",
            "kpi_name": kpi_context.get("kpi_name"),
            "kpi_level": kpi_context.get("kpi_level"),
            "timestamp": kpi_context.get("timestamp") or ui_context.get("incident_timestamp"),
            "node": kpi_context.get("node"),
            "value": kpi_context.get("current_value"),
            "baseline": kpi_context.get("baseline_value"),
            "anomaly_score": kpi_context.get("anomaly_score"),
            "forecast_value": kpi_context.get("forecast_value"),
            "threshold": kpi_context.get("threshold"),
            "description": f"{kpi_context.get('kpi_name', 'The selected KPI')} is in {str(kpi_context.get('status') or 'an anomalous').lower()} state.",
        })
    topology_evidence = [
        {"evidence_id": f"T{index}", "type": "TOPOLOGY", "interface": interface, "components": domain_mapping.components_for_interface(interface)}
        for index, interface in enumerate(related_interfaces, 1)
    ]
    log_context = "\n".join(
        f"[{item['evidence_id']}] {item['@timestamp']} | {item['node']} | {item['severity']} | {item['message']}"
        for item in sorted(evidence, key=lambda row: row["@timestamp"])
    )
    prefix_context = [
        *[f"[{item['evidence_id']}] {item.get('timestamp')} | {item.get('node')} | {item.get('kpi_name')}={item.get('value')} (baseline={item.get('baseline')})" for item in kpi_evidence],
        *[f"[{item['evidence_id']}] interface {item['interface']} connects {', '.join(item['components'])}" for item in topology_evidence],
    ]
    knowledge_context = "\n".join(
        f"[{item['evidence_id']}] {item.get('title')} | {item.get('recommended_action')}"
        for item in knowledge_evidence
    )
    ordered_context = "\n".join([*prefix_context, log_context, knowledge_context]).strip()
    elapsed = max(1, int((time.perf_counter() - started) * 1000))
    return {
        "incident_id": ui_context.get("incident_id"),
        "incident_context": {
            "incident_id": ui_context.get("incident_id"),
            "timestamp": ui_context.get("incident_timestamp") or kpi_context.get("timestamp"),
            "affected_nodes": selected_nodes or ([kpi_context.get("node")] if kpi_context.get("node") else []),
            "severity": (
                (ui_context.get("severity") or [None])[0]
                if isinstance(ui_context.get("severity"), list)
                else ui_context.get("severity") or kpi_context.get("status")
            ),
            "kpi_context": kpi_context or None,
            "related_interfaces": related_interfaces,
            "related_components": related_components,
        },
        "kpi_evidence": kpi_evidence,
        "topology_evidence": topology_evidence,
        "log_evidence": evidence,
        "knowledge_evidence": knowledge_evidence,
        "retrieval_config": {
            "alpha": alpha,
            "top_k": top_k,
            "time_before_minutes": before,
            "time_after_minutes": after,
            "embedding_model": settings.embedding_model,
            "backend": "opensearch_bm25_sentence_transformer_knn",
        },
        "candidate_count": candidate_count,
        # Compatibility alias for existing API consumers and stored analyses.
        "evidence_logs": evidence,
        "ordered_context": ordered_context,
        "retrieval_latency_ms": elapsed,
    }
