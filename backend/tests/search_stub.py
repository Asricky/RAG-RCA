import re
from datetime import datetime


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_-]+", value.lower()))


class SearchStub:
    """Deterministic test double; production always uses OpenSearch."""

    def __init__(self, logs: list[dict]):
        self.logs = logs
        self.last_call: dict = {}

    def hybrid_search(self, query: str, filters: dict, top_k: int, alpha: float, selected_ids: set[str]):
        self.last_call = {"query": query, "filters": filters, "top_k": top_k, "alpha": alpha, "selected_ids": selected_ids}
        rows = list(self.logs)
        if filters.get("nodes"):
            rows = [row for row in rows if row["node"] in filters["nodes"]]
        if filters.get("severities"):
            rows = [row for row in rows if row["severity"] in filters["severities"]]
        for field in ("trace_id", "session_id"):
            if filters.get(field):
                rows = [row for row in rows if row.get(field) == filters[field]]
        if filters.get("time_from"):
            start = datetime.fromisoformat(filters["time_from"])
            rows = [row for row in rows if datetime.fromisoformat(row["@timestamp"].replace("Z", "+00:00")) >= start]
        if filters.get("time_to"):
            end = datetime.fromisoformat(filters["time_to"])
            rows = [row for row in rows if datetime.fromisoformat(row["@timestamp"].replace("Z", "+00:00")) <= end]

        terms = _tokens(query)
        scored = []
        for row in rows:
            document_terms = _tokens(str(row.get("search_text") or row.get("message") or ""))
            overlap = len(terms & document_terms) / max(1, len(terms))
            lexical = overlap
            semantic = min(1.0, overlap + (0.2 if row.get("error_code") and row["error_code"].lower() in query.lower() else 0.0))
            final = min(1.0, alpha * lexical + (1 - alpha) * semantic + (0.12 if row["log_id"] in selected_ids else 0.0))
            scored.append({**row, "bm25_score": round(lexical, 4), "semantic_score": round(semantic, 4), "final_score": round(final, 4)})
        scored.sort(key=lambda row: (row["final_score"], row["@timestamp"]), reverse=True)
        return scored[: max(50, top_k * 5)], len(rows)
