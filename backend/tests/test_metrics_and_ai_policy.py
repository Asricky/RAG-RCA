from pathlib import Path

from app.services.llm import generate_rca
from app.services.metrics import CSVMetricProvider


def demo_kpi_file() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "demo" / "sample_kpi.csv"


def test_empty_raw_directory_falls_back_to_sanitized_demo(tmp_path):
    provider = CSVMetricProvider(demo_file=demo_kpi_file(), raw_dir=tmp_path / "empty", source="raw")
    catalog = provider.list_kpis()
    assert catalog["source"] == "demo-fallback"
    assert catalog["raw_available"] is False
    assert catalog["items"]


def test_missing_private_and_demo_data_is_safe(tmp_path):
    provider = CSVMetricProvider(demo_file=tmp_path / "missing.csv", raw_dir=tmp_path / "empty", source="raw")
    assert provider.list_kpis() == {"source": "empty", "raw_available": False, "items": []}
    assert provider.get_series() == {"source": "empty", "raw_available": False, "items": [], "context": None, "points": []}


def test_ai_abstains_when_kpi_exists_without_log_evidence():
    bundle = {
        "kpi_evidence": [{
            "evidence_id": "K1", "type": "KPI", "kpi_name": "PDU_SESSION_ESTABLISHMENT_SUCCESS_RATE",
            "node": "SMF-01", "value": 82.4, "baseline": 99.2,
        }],
        "topology_evidence": [{"evidence_id": "T1", "type": "TOPOLOGY", "interface": "N4", "components": ["SMF", "UPF"]}],
        "log_evidence": [],
        "knowledge_evidence": [],
    }
    result, _, provider = generate_rca("What caused the KPI degradation?", bundle)
    assert provider == "policy-abstention"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["evidence_strength"] == "LOW"
    assert result["evidence_ids"] == ["K1", "T1"]
    assert "cannot be determined" in result["likely_root_cause"]
