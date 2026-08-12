import base64
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .embeddings import embedding_encoder
from .retrieval import RetrievalUnavailable


class LogStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.logs: list[dict] = []
        self.opensearch_status = "Unavailable"
        self.last_error = ""

    def load(self, path: Path | None = None) -> None:
        source = path or settings.data_dir / "sample_logs.jsonl"
        if source.exists():
            with source.open("r", encoding="utf-8") as handle:
                loaded = [json.loads(line) for line in handle if line.strip()]
            with self._lock:
                self.logs = sorted(loaded, key=lambda item: item["@timestamp"], reverse=True)

    def add_many(self, logs: list[dict]) -> None:
        with self._lock:
            existing = {item["log_id"] for item in self.logs}
            added = [item for item in logs if item["log_id"] not in existing]
            self.logs.extend(added)
            self.logs.sort(key=lambda item: item["@timestamp"], reverse=True)
        if added and self.opensearch_status == "Healthy":
            self.index_documents(added)

    def get(self, log_id: str) -> dict | None:
        return next((item for item in self.logs if item["log_id"] == log_id), None)

    def query(self, filters: dict, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        rows = list(self.logs)
        keyword = str(filters.get("keyword") or "").lower()
        for key in ("node", "component", "severity", "trace_id", "session_id", "error_code"):
            value = filters.get(key)
            if value:
                rows = [row for row in rows if str(row.get(key, "")).lower() == str(value).lower()]
        if keyword:
            rows = [row for row in rows if keyword in row.get("search_text", row.get("message", "")).lower()]
        time_from = _parse_time(filters.get("time_from"))
        time_to = _parse_time(filters.get("time_to"))
        if time_from:
            rows = [row for row in rows if _parse_time(row["@timestamp"]) >= time_from]
        if time_to:
            rows = [row for row in rows if _parse_time(row["@timestamp"]) <= time_to]
        return rows[offset : offset + limit], len(rows)

    def summary(self, rows: list[dict] | None = None) -> dict:
        values = rows or self.logs
        counts = {level: sum(1 for item in values if item["severity"] == level) for level in ("INFO", "WARNING", "ERROR", "CRITICAL")}
        total = max(1, len(values))
        timeline: dict[str, dict] = {}
        for item in values:
            key = item["@timestamp"][11:16]
            slot = timeline.setdefault(key, {"time": key, "total": 0, "errors": 0, "warnings": 0})
            slot["total"] += 1
            slot["errors"] += item["severity"] in ("ERROR", "CRITICAL")
            slot["warnings"] += item["severity"] == "WARNING"
        return {
            "total": len(values),
            "logs_per_minute": round(len(values) / max(1, len(timeline)), 1),
            "error_rate": round((counts["ERROR"] + counts["CRITICAL"]) * 100 / total, 1),
            "warning_rate": round(counts["WARNING"] * 100 / total, 1),
            "severity": counts,
            "timeline": sorted(timeline.values(), key=lambda item: item["time"]),
        }

    def _request(self, method: str, path: str, payload: Any | None = None, content_type: str = "application/json") -> Any:
        data = None if payload is None else (payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8"))
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = content_type
        if settings.opensearch_user:
            credentials = base64.b64encode(f"{settings.opensearch_user}:{settings.opensearch_password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        request = urllib.request.Request(
            f"{settings.opensearch_url.rstrip('/')}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=settings.opensearch_timeout_seconds) as response:
            body = response.read()
            return json.loads(body) if body else {}

    def ensure_opensearch(self) -> None:
        self.opensearch_status = "Initializing"
        try:
            self._request("GET", "/")
            embedding_encoder.load()
            try:
                self._request("HEAD", f"/{settings.opensearch_index}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                self._request("PUT", f"/{settings.opensearch_index}", self._index_mapping())
            self._validate_index()
            self.index_documents(self.logs)
            self.opensearch_status = "Healthy"
            self.last_error = ""
        except Exception as exc:
            self.opensearch_status = "Unavailable"
            self.last_error = str(exc)

    def _index_mapping(self) -> dict:
        return {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "_meta": {
                    "embedding_model": settings.embedding_model,
                    "embedding_dimension": settings.embedding_dimension,
                },
                "properties": {
                    "log_id": {"type": "keyword"},
                    "@timestamp": {"type": "date"},
                    "node": {"type": "keyword"},
                    "component": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "message": {"type": "text"},
                    "trace_id": {"type": "keyword"},
                    "session_id": {"type": "keyword"},
                    "error_code": {"type": "keyword"},
                    "search_text": {"type": "text"},
                    "metadata": {"type": "object"},
                    "embedding_model": {"type": "keyword"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": settings.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene",
                            "parameters": {"ef_construction": 128, "m": 16},
                        },
                    },
                },
            },
        }

    def _validate_index(self) -> None:
        mapping = self._request("GET", f"/{settings.opensearch_index}/_mapping")
        current = mapping.get(settings.opensearch_index, {}).get("mappings", {})
        vector = current.get("properties", {}).get("embedding", {})
        metadata = current.get("_meta", {})
        if vector.get("dimension") != settings.embedding_dimension or metadata.get("embedding_model") != settings.embedding_model:
            raise RuntimeError(
                f"Index {settings.opensearch_index} tidak kompatibel dengan {settings.embedding_model}. "
                "Gunakan nama OPENSEARCH_INDEX baru atau recreate index tersebut."
            )

    def index_documents(self, logs: list[dict]) -> None:
        if not logs:
            return
        texts = [str(item.get("search_text") or item.get("message") or "") for item in logs]
        vectors = embedding_encoder.encode_documents(texts)
        lines: list[str] = []
        for item, vector in zip(logs, vectors):
            lines.append(json.dumps({"index": {"_index": settings.opensearch_index, "_id": item["log_id"]}}))
            document = dict(item)
            document["embedding"] = vector
            document["embedding_model"] = settings.embedding_model
            lines.append(json.dumps(document))
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        result = self._request("POST", "/_bulk?refresh=true", payload, "application/x-ndjson")
        if result.get("errors"):
            failures = [item for row in result.get("items", []) for item in row.values() if item.get("error")]
            raise RuntimeError(f"OpenSearch bulk indexing gagal untuk {len(failures)} dokumen")

    @staticmethod
    def _filter_clauses(filters: dict) -> list[dict]:
        clauses: list[dict] = []
        if filters.get("nodes"):
            clauses.append({"terms": {"node": filters["nodes"]}})
        if filters.get("severities"):
            clauses.append({"terms": {"severity": filters["severities"]}})
        for key in ("trace_id", "session_id"):
            if filters.get(key):
                clauses.append({"term": {key: filters[key]}})
        bounds = {}
        if filters.get("time_from"):
            bounds["gte"] = filters["time_from"]
        if filters.get("time_to"):
            bounds["lte"] = filters["time_to"]
        if bounds:
            clauses.append({"range": {"@timestamp": bounds}})
        return clauses

    @staticmethod
    def _normalise(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        low, high = min(scores.values()), max(scores.values())
        if high == low:
            return {key: 1.0 if high > 0 else 0.0 for key in scores}
        return {key: (value - low) / (high - low) for key, value in scores.items()}

    def hybrid_search(self, query: str, filters: dict, top_k: int, alpha: float, selected_ids: set[str]) -> tuple[list[dict], int]:
        if self.opensearch_status != "Healthy":
            detail = f": {self.last_error}" if self.last_error else ""
            raise RetrievalUnavailable(f"OpenSearch retrieval belum siap{detail}")
        candidate_size = min(500, max(50, top_k * 5))
        clauses = self._filter_clauses(filters)
        filter_query = {"bool": {"filter": clauses}} if clauses else {"match_all": {}}
        source = {"excludes": ["embedding"]}
        bm25_query = {
            "size": candidate_size,
            "_source": source,
            "query": {
                "bool": {
                    "must": [{"multi_match": {
                        "query": query,
                        "fields": ["search_text^3", "message^2", "error_code^2", "node", "component"],
                        "type": "best_fields",
                    }}],
                    "filter": clauses,
                }
            },
        }
        vector = embedding_encoder.encode_query(query)
        knn_parameters: dict[str, Any] = {"vector": vector, "k": candidate_size}
        if clauses:
            knn_parameters["filter"] = {"bool": {"filter": clauses}}
        knn_query = {"size": candidate_size, "_source": source, "query": {"knn": {"embedding": knn_parameters}}}

        bm25_response = self._request("POST", f"/{settings.opensearch_index}/_search", bm25_query)
        knn_response = self._request("POST", f"/{settings.opensearch_index}/_search", knn_query)
        count_response = self._request("POST", f"/{settings.opensearch_index}/_count", {"query": filter_query})
        bm25_hits = bm25_response.get("hits", {}).get("hits", [])
        knn_hits = knn_response.get("hits", {}).get("hits", [])
        documents = {hit["_id"]: hit["_source"] for hit in [*bm25_hits, *knn_hits]}
        bm25_raw = {hit["_id"]: float(hit.get("_score") or 0) for hit in bm25_hits}
        knn_raw = {hit["_id"]: float(hit.get("_score") or 0) for hit in knn_hits}

        if selected_ids:
            selected = self._request("POST", f"/{settings.opensearch_index}/_mget", {"ids": sorted(selected_ids), "_source": source})
            for item in selected.get("docs", []):
                if item.get("found"):
                    documents[item["_id"]] = item["_source"]

        bm25 = self._normalise(bm25_raw)
        semantic = self._normalise(knn_raw)
        ranked: list[dict] = []
        for log_id, document in documents.items():
            lexical_score = bm25.get(log_id, 0.0)
            semantic_score = semantic.get(log_id, 0.0)
            selected_boost = 0.12 if log_id in selected_ids else 0.0
            final_score = min(1.0, alpha * lexical_score + (1 - alpha) * semantic_score + selected_boost)
            ranked.append({
                **document,
                "bm25_score": round(lexical_score, 4),
                "semantic_score": round(semantic_score, 4),
                "final_score": round(final_score, 4),
                "bm25_raw_score": round(bm25_raw.get(log_id, 0.0), 4),
                "knn_raw_score": round(knn_raw.get(log_id, 0.0), 4),
            })
        ranked.sort(key=lambda item: (item["final_score"], item.get("@timestamp", "")), reverse=True)
        return ranked, int(count_response.get("count", len(documents)))


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


log_store = LogStore()
