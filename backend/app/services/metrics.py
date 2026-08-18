import csv
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ..config import settings
from .domain_mapping import domain_mapping


class MetricsProvider(Protocol):
    def list_kpis(self) -> dict: ...

    def get_series(self, kpi_name: str | None = None, node: str | None = None, limit: int = 240) -> dict: ...


def _number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _timestamp(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    parsed = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%m/%d/%Y %H:%M"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _split(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").replace(";", ",").split(",") if item.strip()]


def _kpi_from_filename(path: Path) -> str:
    label = re.sub(r"-\d{8}-\d{8}$", "", path.stem)
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper()


class CSVMetricProvider:
    """Read sanitized long-form demo KPI data or local-only wide historical CSV files."""

    def __init__(self, demo_file: Path | None = None, raw_dir: Path | None = None, source: str | None = None):
        self.demo_file = demo_file or settings.kpi_demo_file
        self.raw_dir = raw_dir or settings.kpi_raw_dir
        self.requested_source = (source or settings.kpi_source).lower()
        self._lock = threading.Lock()
        self._signature: tuple | None = None
        self._points: list[dict] = []
        self._source = "empty"

    def _files(self) -> tuple[list[Path], str]:
        raw_files = sorted(self.raw_dir.rglob("*.csv")) if self.raw_dir.exists() else []
        if self.requested_source == "raw" and raw_files:
            return raw_files, "raw"
        if self.demo_file.exists():
            return [self.demo_file], "demo" if self.requested_source == "demo" else "demo-fallback"
        return [], "empty"

    def _load_long(self, path: Path) -> list[dict]:
        points: list[dict] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                timestamp = _timestamp(row.get("timestamp") or row.get("Time"))
                value = _number(row.get("value"))
                kpi_name = str(row.get("kpi_name") or "").strip()
                node = str(row.get("node") or "").strip()
                if not timestamp or value is None or not kpi_name or not node:
                    continue
                enrichment = domain_mapping.enrich(
                    kpi_name,
                    kpi_level=str(row.get("kpi_level") or "").strip() or None,
                    related_interfaces=_split(row.get("related_interfaces")),
                    related_components=_split(row.get("related_components")),
                )
                points.append({
                    "scenario_id": str(row.get("scenario_id") or "").strip() or None,
                    "timestamp": timestamp,
                    "kpi_name": kpi_name,
                    "kpi_level": enrichment["kpi_level"],
                    "node": node,
                    "value": value,
                    "baseline_value": _number(row.get("baseline_value")),
                    "anomaly_score": _number(row.get("anomaly_score")),
                    "forecast_value": _number(row.get("forecast_value")),
                    "threshold": _number(row.get("threshold")),
                    "status": str(row.get("status") or "NORMAL").strip().upper(),
                    "related_interfaces": enrichment["related_interfaces"],
                    "related_components": enrichment["related_components"],
                })
        return points

    def _load_wide(self, path: Path) -> list[dict]:
        points: list[dict] = []
        kpi_name = _kpi_from_filename(path)
        enrichment = domain_mapping.resolve(kpi_name)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return points
            time_column = next((field for field in reader.fieldnames if field.lower() in {"time", "timestamp", "date"}), reader.fieldnames[0])
            nodes = [field for field in reader.fieldnames if field != time_column]
            for row in reader:
                timestamp = _timestamp(row.get(time_column))
                if not timestamp:
                    continue
                for node in nodes:
                    value = _number(row.get(node))
                    if value is None:
                        continue
                    points.append({
                        "scenario_id": None,
                        "timestamp": timestamp,
                        "kpi_name": kpi_name,
                        "kpi_level": enrichment["kpi_level"],
                        "node": node,
                        "value": value,
                        "baseline_value": None,
                        "anomaly_score": None,
                        "forecast_value": None,
                        "threshold": None,
                        "status": "HISTORICAL",
                        "related_interfaces": enrichment["related_interfaces"],
                        "related_components": enrichment["related_components"],
                    })
        return points

    def _refresh(self) -> None:
        files, source = self._files()
        signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files)
        if signature == self._signature and source == self._source:
            return
        with self._lock:
            if signature == self._signature and source == self._source:
                return
            points: list[dict] = []
            for path in files:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    fields = next(csv.reader(handle), [])
                points.extend(self._load_long(path) if "kpi_name" in fields and "value" in fields else self._load_wide(path))
            self._points = sorted(points, key=lambda item: item["timestamp"])
            self._signature = signature
            self._source = source

    @property
    def raw_available(self) -> bool:
        return self.raw_dir.exists() and any(self.raw_dir.rglob("*.csv"))

    def list_kpis(self) -> dict:
        self._refresh()
        grouped: dict[tuple[str, str], list[dict]] = {}
        for point in self._points:
            grouped.setdefault((point["kpi_name"], point["node"]), []).append(point)
        items = []
        for (kpi_name, node), rows in grouped.items():
            latest = rows[-1]
            focus = max(rows, key=lambda row: row.get("anomaly_score") if row.get("anomaly_score") is not None else -1.0)
            if focus.get("anomaly_score") is None:
                focus = latest
            items.append({
                "kpi_name": kpi_name,
                "scenario_id": focus.get("scenario_id"),
                "kpi_level": focus.get("kpi_level"),
                "node": node,
                "timestamp": focus["timestamp"],
                "current_value": focus["value"],
                "baseline_value": focus.get("baseline_value"),
                "anomaly_score": focus.get("anomaly_score"),
                "forecast_value": focus.get("forecast_value"),
                "threshold": focus.get("threshold"),
                "status": focus.get("status"),
                "related_interfaces": focus.get("related_interfaces", []),
                "related_components": focus.get("related_components", []),
                "point_count": len(rows),
                "time_from": rows[0]["timestamp"],
                "time_to": rows[-1]["timestamp"],
            })
        items.sort(key=lambda item: (item["kpi_name"], item["node"]))
        return {"source": self._source, "raw_available": self.raw_available, "items": items}

    def get_series(self, kpi_name: str | None = None, node: str | None = None, limit: int = 240) -> dict:
        catalog = self.list_kpis()
        selected = next((item for item in catalog["items"] if (not kpi_name or item["kpi_name"] == kpi_name) and (not node or item["node"] == node)), None)
        if selected is None:
            return {**catalog, "context": None, "points": []}
        rows = [point for point in self._points if point["kpi_name"] == selected["kpi_name"] and point["node"] == selected["node"]]
        return {"source": catalog["source"], "raw_available": catalog["raw_available"], "context": selected, "points": rows[-limit:]}


metrics_provider = CSVMetricProvider()
