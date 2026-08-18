import json
from pathlib import Path
from app.services.retrieval import retrieve
from tests.search_stub import SearchStub

def sample_logs():
    path=Path(__file__).resolve().parents[2]/"data"/"demo"/"sample_logs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]

def test_pfcp_evidence_is_ranked():
    backend = SearchStub(sample_logs())
    bundle=retrieve(backend,"PFCP timeout root cause",{"selected_nodes":["SMF-01","UPF-01"],"incident_timestamp":"2026-08-12T10:03:24Z"},{"alpha":.5,"top_k":10})
    ids={item["log_id"] for item in bundle["evidence_logs"]}
    assert "LOG-0034" in ids
    assert all(item["evidence_id"]==f"L{i}" for i,item in enumerate(bundle["log_evidence"],1))
    assert all(0<=item["final_score"]<=1 for item in bundle["evidence_logs"])
    assert bundle["retrieval_config"]["backend"] == "opensearch_bm25_sentence_transformer_knn"
    assert backend.last_call["filters"]["nodes"] == ["SMF-01", "UPF-01"]

def test_context_filtering():
    bundle=retrieve(SearchStub(sample_logs()),"registration failure",{"selected_nodes":["AMF-02"],"incident_timestamp":"2026-08-12T10:17:48Z"},{"top_k":5})
    assert bundle["candidate_count"]>0
    assert all(item["node"]=="AMF-02" for item in bundle["evidence_logs"])

def test_kpi_and_topology_evidence_are_preserved():
    backend = SearchStub(sample_logs())
    kpi_context = {
        "kpi_name": "PDU_SESSION_ESTABLISHMENT_SUCCESS_RATE",
        "kpi_level": "NETWORK_FUNCTION",
        "node": "SMF-01",
        "timestamp": "2026-08-12T10:03:24Z",
        "current_value": 82.4,
        "baseline_value": 99.2,
        "anomaly_score": 0.96,
        "status": "CRITICAL",
        "related_interfaces": ["N4"],
        "related_components": ["SMF", "UPF"],
    }
    bundle = retrieve(backend, "What caused the KPI degradation?", {"kpi_context": kpi_context}, {"top_k": 5})
    assert bundle["kpi_evidence"][0]["evidence_id"] == "K1"
    assert bundle["topology_evidence"][0]["evidence_id"] == "T1"
    assert bundle["topology_evidence"][0]["interface"] == "N4"
    assert backend.last_call["filters"]["components"] == ["SMF", "UPF"]
    assert "K1" in bundle["ordered_context"] and "T1" in bundle["ordered_context"]
