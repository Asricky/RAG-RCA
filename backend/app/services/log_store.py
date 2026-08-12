import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .retrieval import embed_text


class LogStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.logs: list[dict] = []
        self.opensearch_status = "Unavailable"

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
            self.logs.extend(item for item in logs if item["log_id"] not in existing)
            self.logs.sort(key=lambda item: item["@timestamp"], reverse=True)

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

    def ensure_opensearch(self) -> None:
        mapping = {
            "settings": {"index": {"knn": True}},
            "mappings": {"properties": {
                "log_id": {"type": "keyword"}, "@timestamp": {"type": "date"}, "node": {"type": "keyword"},
                "component": {"type": "keyword"}, "severity": {"type": "keyword"}, "message": {"type": "text"},
                "trace_id": {"type": "keyword"}, "session_id": {"type": "keyword"}, "error_code": {"type": "keyword"},
                "search_text": {"type": "text"}, "metadata": {"type": "object"},
                "embedding": {"type": "knn_vector", "dimension": settings.embedding_dimension},
            }},
        }
        try:
            request = urllib.request.Request(f"{settings.opensearch_url}/{settings.opensearch_index}", method="HEAD")
            try:
                urllib.request.urlopen(request, timeout=3).read()
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                create = urllib.request.Request(
                    f"{settings.opensearch_url}/{settings.opensearch_index}",
                    data=json.dumps(mapping).encode(), headers={"Content-Type": "application/json"}, method="PUT"
                )
                urllib.request.urlopen(create, timeout=10).read()
            if self.logs:
                lines: list[str] = []
                for item in self.logs:
                    lines.append(json.dumps({"index": {"_index": settings.opensearch_index, "_id": item["log_id"]}}))
                    document = dict(item)
                    document["embedding"] = embed_text(document["search_text"], settings.embedding_dimension)
                    lines.append(json.dumps(document))
                bulk = urllib.request.Request(
                    f"{settings.opensearch_url}/_bulk?refresh=true", data=("\n".join(lines) + "\n").encode(),
                    headers={"Content-Type": "application/x-ndjson"}, method="POST"
                )
                urllib.request.urlopen(bulk, timeout=30).read()
            self.opensearch_status = "Healthy"
        except Exception:
            self.opensearch_status = "Unavailable"


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

