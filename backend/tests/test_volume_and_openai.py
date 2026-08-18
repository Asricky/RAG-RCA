import io
import json
from app.config import settings
from app.services.dataset_ingestion import iter_staged_logs, stage_upload
from app.services.llm import _generate_openai
from app.services.log_store import LogStore


def log_row(index: int) -> dict:
    return {
        "@timestamp": f"2026-08-12T10:{index % 60:02d}:00Z",
        "node": "SMF-01",
        "component": "SMF",
        "severity": "ERROR",
        "message": f"PFCP timeout row {index}",
        "error_code": "PFCP_TIMEOUT",
    }


def test_jsonl_upload_is_staged_incrementally(tmp_path):
    original_storage = settings.dataset_storage_dir
    object.__setattr__(settings, "dataset_storage_dir", tmp_path)
    try:
        payload = b"".join((json.dumps(log_row(index)) + "\n").encode() for index in range(2500))
        result = stage_upload(io.BytesIO(payload), "volume.jsonl", "dataset-volume")
        assert result.total == 2500
        assert result.valid == 2500
        assert len(result.preview) == 10
        staged = list(iter_staged_logs("dataset-volume"))
        assert len(staged) == 2500
        assert staged[0]["source_dataset_id"] == "dataset-volume"
        assert staged[-1]["log_id"] == "UPL-DATASETV-0000002500"
    finally:
        object.__setattr__(settings, "dataset_storage_dir", original_storage)


def test_opensearch_bulk_payload_is_bounded_by_batch_size(monkeypatch):
    store = LogStore()
    requests: list[bytes] = []
    original_batch_size = settings.index_batch_size
    object.__setattr__(settings, "index_batch_size", 128)
    try:
        monkeypatch.setattr("app.services.log_store.embedding_encoder.encode_documents", lambda rows: [[0.1] * 384 for _ in rows])

        def request(method, path, payload=None, content_type="application/json"):
            requests.append(payload)
            return {"errors": False}

        monkeypatch.setattr(store, "_request", request)
        documents = [{**log_row(index), "log_id": f"LOG-{index}"} for index in range(300)]
        assert store.index_documents(documents, refresh=False) == 300
        assert len(requests) == 3
        assert [len(payload.decode().strip().splitlines()) // 2 for payload in requests] == [128, 128, 44]
    finally:
        object.__setattr__(settings, "index_batch_size", original_batch_size)


def test_openai_responses_request_uses_gpt_56_sol_and_strict_schema(monkeypatch):
    captured: dict = {}
    originals = {key: getattr(settings, key) for key in ("openai_api_key", "openai_model", "openai_reasoning_effort")}
    object.__setattr__(settings, "openai_api_key", "test-key-not-a-secret")
    object.__setattr__(settings, "openai_model", "gpt-5.6-sol")
    object.__setattr__(settings, "openai_reasoning_effort", "medium")
    result = {
        "status": "SUPPORTED",
        "incident_summary": "A PFCP timeout was detected.",
        "likely_root_cause": "The PFCP heartbeat failed.",
        "affected_components": ["SMF-01", "UPF-01"],
        "affected_interfaces": ["N4"],
        "reasoning_summary": "L1 records the timeout.",
        "evidence_ids": ["L1"],
        "recommended_investigation": ["Check the PFCP association."],
        "suggested_resolution": [],
        "evidence_strength": "HIGH",
    }

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self):
            return json.dumps({"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}).encode()

    def urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return Response()

    monkeypatch.setattr("app.services.llm.urllib.request.urlopen", urlopen)
    try:
        output = _generate_openai("What is the root cause?", {"log_evidence": [{"evidence_id": "L1", **log_row(1), "final_score": 0.9}]})
        assert output["evidence_ids"] == ["L1"]
        assert captured["model"] == "gpt-5.6-sol"
        assert captured["reasoning"] == {"effort": "medium"}
        assert captured["text"]["format"]["type"] == "json_schema"
        assert captured["text"]["format"]["strict"] is True
        assert captured["store"] is False
    finally:
        for key, value in originals.items(): object.__setattr__(settings, key, value)
