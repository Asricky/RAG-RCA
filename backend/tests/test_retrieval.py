import json
from pathlib import Path
from app.services.retrieval import retrieve

def sample_logs():
    path=Path(__file__).resolve().parents[2]/"data"/"sample_logs.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]

def test_pfcp_evidence_is_ranked():
    bundle=retrieve(sample_logs(),"PFCP timeout root cause",{"selected_nodes":["SMF-01","UPF-01"],"incident_timestamp":"2026-08-12T10:03:24Z"},{"alpha":.5,"top_k":10})
    ids={item["log_id"] for item in bundle["evidence_logs"]}
    assert "LOG-0034" in ids
    assert all(item["evidence_id"]==f"E{i}" for i,item in enumerate(bundle["evidence_logs"],1))
    assert all(0<=item["final_score"]<=1 for item in bundle["evidence_logs"])

def test_context_filtering():
    bundle=retrieve(sample_logs(),"registration failure",{"selected_nodes":["AMF-02"],"incident_timestamp":"2026-08-12T10:17:48Z"},{"top_k":5})
    assert bundle["candidate_count"]>0
    assert all(item["node"]=="AMF-02" for item in bundle["evidence_logs"])

