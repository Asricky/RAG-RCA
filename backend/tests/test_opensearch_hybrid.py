from app.services.log_store import LogStore


def document(log_id: str, timestamp: str) -> dict:
    return {
        "log_id": log_id,
        "@timestamp": timestamp,
        "node": "SMF-01",
        "component": "SMF",
        "severity": "ERROR",
        "message": f"PFCP failure {log_id}",
        "trace_id": "trace-1",
        "session_id": "session-1",
        "error_code": "PFCP_TIMEOUT",
    }


def test_vector_mapping_uses_lucene_hnsw():
    vector = LogStore()._index_mapping()["mappings"]["properties"]["embedding"]
    assert vector["type"] == "knn_vector"
    assert vector["dimension"] == 384
    assert vector["method"]["name"] == "hnsw"
    assert vector["method"]["engine"] == "lucene"
    assert vector["method"]["space_type"] == "cosinesimil"


def test_hybrid_search_uses_bm25_and_sentence_transformer_knn(monkeypatch):
    store = LogStore()
    store.opensearch_status = "Healthy"
    requests: list[tuple[str, dict]] = []
    docs = {
        "LOG-A": document("LOG-A", "2026-08-12T10:00:00Z"),
        "LOG-B": document("LOG-B", "2026-08-12T10:01:00Z"),
        "LOG-C": document("LOG-C", "2026-08-12T10:02:00Z"),
    }

    def request(method, path, payload=None, content_type="application/json"):
        requests.append((path, payload))
        if path.endswith("/_count"):
            return {"count": 3}
        if path.endswith("/_mget"):
            return {"docs": []}
        if path.endswith("/_search") and "knn" in payload["query"]:
            return {"hits": {"hits": [
                {"_id": "LOG-C", "_score": 1.9, "_source": docs["LOG-C"]},
                {"_id": "LOG-A", "_score": 1.5, "_source": docs["LOG-A"]},
            ]}}
        if path.endswith("/_search"):
            return {"hits": {"hits": [
                {"_id": "LOG-A", "_score": 8.0, "_source": docs["LOG-A"]},
                {"_id": "LOG-B", "_score": 2.0, "_source": docs["LOG-B"]},
            ]}}
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(store, "_request", request)
    monkeypatch.setattr("app.services.log_store.embedding_encoder.encode_query", lambda _: [0.1] * 384)
    ranked, count = store.hybrid_search(
        "PFCP timeout",
        {"nodes": ["SMF-01"], "severities": ["ERROR"], "trace_id": None, "session_id": None, "time_from": None, "time_to": None},
        top_k=5,
        alpha=0.5,
        selected_ids=set(),
    )

    assert count == 3
    assert {item["log_id"] for item in ranked} == {"LOG-A", "LOG-B", "LOG-C"}
    assert ranked[0]["log_id"] in {"LOG-A", "LOG-C"}
    search_payloads = [payload for path, payload in requests if path.endswith("/_search")]
    assert any("multi_match" in payload["query"]["bool"]["must"][0] for payload in search_payloads if "bool" in payload["query"])
    knn = next(payload["query"]["knn"]["embedding"] for payload in search_payloads if "knn" in payload["query"])
    assert len(knn["vector"]) == 384
    assert knn["filter"] == {"bool": {"filter": [{"terms": {"node": ["SMF-01"]}}, {"terms": {"severity": ["ERROR"]}}]}}
