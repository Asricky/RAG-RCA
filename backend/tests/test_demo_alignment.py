import json
from pathlib import Path

from app.services.llm import generate_rca
from app.services.metrics import CSVMetricProvider
from app.services.retrieval import retrieve
from tests.search_stub import SearchStub


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "data" / "demo"


def load_json(name: str):
    return json.loads((DEMO / name).read_text(encoding="utf-8"))


def load_logs() -> list[dict]:
    return [json.loads(line) for line in (DEMO / "sample_logs.jsonl").read_text(encoding="utf-8").splitlines()]


class KnowledgeStub:
    """Deterministic stand-in for the separate OpenSearch knowledge index."""

    def __init__(self):
        self.documents = load_json("sample_knowledge.json")

    def search(self, query, *, interfaces, components, error_codes, limit=None):
        terms = {term.lower() for term in [*interfaces, *components, *error_codes]}
        ranked = []
        for document in self.documents:
            values = [*document["interfaces"], *document["components"], *document["error_codes"]]
            score = sum(value.lower() in terms for value in values)
            score += sum(phrase.lower() in query.lower() for phrase in document["symptoms"])
            if score:
                ranked.append(({**document, "knowledge_score": float(score)}, score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        rows = [item[0] for item in ranked[: limit or 3]]
        exact = [item for item in rows if set(error_codes) & set(item["error_codes"])]
        return exact or [item for item in rows if set(interfaces) & set(item["interfaces"])]


def scenario_bundle(incident_code: str) -> tuple[dict, dict]:
    truth = next(item for item in load_json("sample_ground_truth.json") if item["incident_code"] == incident_code)
    incident = next(item for item in load_json("sample_incidents.json") if item["incident_code"] == incident_code)
    kpis = CSVMetricProvider(demo_file=DEMO / "sample_kpi.csv", raw_dir=DEMO / "does-not-exist", source="demo").list_kpis()["items"]
    kpi = next(item for item in kpis if item["kpi_name"] == truth["kpi_name"])
    bundle = retrieve(
        SearchStub(load_logs()),
        truth["question"],
        {"incident_id": incident_code, "incident_timestamp": incident["incident_timestamp"], "kpi_context": kpi},
        {"top_k": 10, "alpha": 0.5},
        KnowledgeStub(),
    )
    return truth, bundle


def test_scenario_01_retrieves_logs_and_resolution_then_mock_derives_rca():
    truth, bundle = scenario_bundle("INC-001")
    retrieved = {item["log_id"] for item in bundle["log_evidence"]}
    assert set(truth["evidence_log_ids"]) <= retrieved
    assert set(bundle["incident_context"]["related_interfaces"]) == set(truth["expected_interfaces"])
    assert bundle["knowledge_evidence"][0]["document_id"] == "KB-PFCP-001"
    assert len(bundle["knowledge_evidence"]) == 1

    result, _, provider = generate_rca(truth["question"], bundle)
    assert provider == "mock"
    assert result["status"] == "SUPPORTED"
    assert "[L" in result["likely_root_cause"]
    assert result["suggested_resolution"]
    assert result["suggested_resolution"][0]["knowledge_sources"] == ["R1"]
    assert len(result["suggested_resolution"]) == 1
    assert set(result["evidence_ids"]) <= {
        item["evidence_id"]
        for field in ("kpi_evidence", "topology_evidence", "log_evidence", "knowledge_evidence")
        for item in bundle[field]
    }


def test_insufficient_evidence_scenario_abstains_despite_kpi_anomaly():
    truth, bundle = scenario_bundle("INC-004")
    result, _, provider = generate_rca(truth["question"], bundle)
    assert provider == "policy-abstention"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["evidence_strength"] == "LOW"
    assert result["suggested_resolution"] == []
    assert "cannot be determined" in result["likely_root_cause"]
