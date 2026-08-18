import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Iterable

from ..config import settings


MAX_RECORD_BYTES = 1024 * 1024


class DatasetUploadError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class IngestionResult:
    total: int
    valid: int
    rejected: int
    preview: list[dict]
    staged_path: Path


def dataset_path(dataset_id: str) -> Path:
    return settings.dataset_storage_dir / f"{dataset_id}.jsonl"


def _file_size(handle: BinaryIO) -> int:
    current = handle.tell()
    handle.seek(0, 2)
    size = handle.tell()
    handle.seek(current)
    return size


def _normalise(raw: object, dataset_id: str, row_number: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    aliases = {"source_time": "@timestamp", "network_function": "component", "instance": "node", "log_level": "severity", "body": "message"}
    values = {aliases.get(str(key), str(key)): value for key, value in raw.items()}
    if not all(values.get(key) for key in ("@timestamp", "node", "component", "severity", "message")):
        return None
    try:
        timestamp = datetime.fromisoformat(str(values["@timestamp"]).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    severity = str(values["severity"]).upper()
    if severity not in {"INFO", "WARNING", "ERROR", "MAJOR", "CRITICAL"}:
        return None
    node = str(values["node"])
    component = str(values["component"]).upper()
    message = str(values["message"])
    if len(node) > 255 or len(component) > 50 or len(message) > 10_000:
        return None
    metadata = values.get("metadata") if isinstance(values.get("metadata"), dict) else {}
    try:
        if len(json.dumps(metadata, ensure_ascii=False)) > 8192:
            metadata = {}
    except (TypeError, ValueError):
        metadata = {}
    original_log_id = str(values.get("log_id") or "")[:255]
    dataset_token = "".join(character for character in dataset_id if character.isalnum())[:8].upper()
    log_id = f"UPL-{dataset_token}-{row_number:010d}"
    item = {
        "log_id": log_id,
        "original_log_id": original_log_id,
        "dataset_id": dataset_id,
        "source_dataset_id": dataset_id,
        "@timestamp": timestamp.isoformat(),
        "node": node,
        "component": component,
        "severity": severity,
        "message": message,
        "trace_id": str(values.get("trace_id") or "")[:255],
        "session_id": str(values.get("session_id") or "")[:255],
        "error_code": str(values.get("error_code") or "")[:255],
        "metadata": metadata,
    }
    item["search_text"] = f"[{node}] [{severity}] [{item['error_code']}] {message}"
    return item


def _rows(handle: BinaryIO, suffix: str, size: int) -> Iterable[object]:
    if suffix == ".jsonl":
        line_number = 0
        while True:
            raw_line = handle.readline(MAX_RECORD_BYTES + 1)
            if not raw_line:
                break
            line_number += 1
            if len(raw_line) > MAX_RECORD_BYTES and not raw_line.endswith(b"\n"):
                raise DatasetUploadError(413, f"The JSONL record on line {line_number} exceeds the 1 MB limit")
            try:
                line = raw_line.decode("utf-8-sig" if line_number == 1 else "utf-8")
                if line.strip():
                    yield json.loads(line)
            except UnicodeDecodeError as exc:
                raise DatasetUploadError(400, "The file must use UTF-8 encoding") from exc
            except json.JSONDecodeError as exc:
                raise DatasetUploadError(400, f"Invalid JSONL on line {line_number}") from exc
        return
    text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
    try:
        if suffix == ".csv":
            csv.field_size_limit(MAX_RECORD_BYTES)
            yield from csv.DictReader(text)
        elif suffix == ".json":
            if size > 25 * 1024 * 1024:
                raise DatasetUploadError(413, "JSON arrays larger than 25 MB must be converted to JSONL for streaming processing")
            payload = json.load(text)
            if not isinstance(payload, list):
                raise DatasetUploadError(400, "The JSON root must be an array")
            yield from payload
        else:
            raise DatasetUploadError(400, "Only CSV, JSON, and JSONL files are supported")
    except UnicodeDecodeError as exc:
        raise DatasetUploadError(400, "The file must use UTF-8 encoding") from exc
    except csv.Error as exc:
        raise DatasetUploadError(400, "Invalid CSV format") from exc
    except json.JSONDecodeError as exc:
        raise DatasetUploadError(400, "Invalid JSON format") from exc
    finally:
        text.detach()


def stage_upload(handle: BinaryIO, filename: str, dataset_id: str) -> IngestionResult:
    size = _file_size(handle)
    if size > settings.max_upload_bytes:
        raise DatasetUploadError(413, f"The file exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    suffix = Path(filename).suffix.lower()
    settings.dataset_storage_dir.mkdir(parents=True, exist_ok=True)
    staged = dataset_path(dataset_id)
    preview: list[dict] = []
    valid = rejected = total = 0
    handle.seek(0)
    try:
        with staged.open("w", encoding="utf-8", newline="\n") as output:
            for row_number, raw in enumerate(_rows(handle, suffix, size), 1):
                total += 1
                if total > settings.max_dataset_records:
                    raise DatasetUploadError(413, f"The dataset exceeds the {settings.max_dataset_records:,}-record limit")
                item = _normalise(raw, dataset_id, row_number)
                if item is None:
                    rejected += 1
                    continue
                valid += 1
                if len(preview) < 10:
                    preview.append(item)
                output.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    if valid == 0:
        staged.unlink(missing_ok=True)
        raise DatasetUploadError(400, "The dataset contains no valid records")
    return IngestionResult(total=total, valid=valid, rejected=rejected, preview=preview, staged_path=staged)


def iter_staged_logs(dataset_id: str) -> Iterable[dict]:
    path = dataset_path(dataset_id)
    if not path.exists():
        raise FileNotFoundError("The staged dataset file was not found")
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)
