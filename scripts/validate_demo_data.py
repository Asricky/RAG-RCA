"""Validate the synthetic dataset without reading any private raw-data directory."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
DOMAIN = ROOT / "config" / "domain"


def load_json(name: str):
    return json.loads((DEMO / name).read_text(encoding="utf-8"))


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> dict[str, int]:
    required = {
        "sample_logs.jsonl", "sample_kpi.csv", "sample_incidents.json",
        "sample_ground_truth.json", "sample_knowledge.json", "sample_scenarios.json",
    }
    missing = sorted(name for name in required if not (DEMO / name).is_file())
    require(not missing, f"Missing demo files: {', '.join(missing)}")

    logs = [json.loads(line) for line in (DEMO / "sample_logs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    with (DEMO / "sample_kpi.csv").open(encoding="utf-8", newline="") as handle:
        kpis = list(csv.DictReader(handle))
    incidents = load_json("sample_incidents.json")
    truths = load_json("sample_ground_truth.json")
    knowledge = load_json("sample_knowledge.json")
    scenarios = load_json("sample_scenarios.json")
    kpi_mapping = json.loads((DOMAIN / "kpi_mapping.json").read_text(encoding="utf-8"))
    interface_mapping = json.loads((DOMAIN / "interface_mapping.json").read_text(encoding="utf-8"))

    require(len(logs) == 400, "The demo must contain exactly 400 deterministic log records")
    require(len(kpis) == 240, "The demo must contain four 60-point KPI series")
    require(len(incidents) == len(truths) == len(scenarios) == 4, "Incident, truth, and scenario counts must match")
    require(len(knowledge) == 3, "The demo must contain three resolution documents")

    def unique(rows: list[dict], field: str) -> dict[str, dict]:
        values = [row[field] for row in rows]
        require(len(values) == len(set(values)), f"Duplicate {field} values are not allowed")
        return {row[field]: row for row in rows}

    logs_by_id = unique(logs, "log_id")
    incidents_by_id = unique(incidents, "incident_code")
    truth_by_id = unique(truths, "incident_code")
    knowledge_by_id = unique(knowledge, "document_id")
    scenario_by_id = unique(scenarios, "incident_code")
    require(set(incidents_by_id) == set(truth_by_id) == set(scenario_by_id), "Scenario joins are incomplete")

    require(all(log.get("metadata", {}).get("synthetic") is True for log in logs), "Every demo log must be marked synthetic")
    require(all(document.get("metadata", {}).get("synthetic") is True for document in knowledge), "Every knowledge document must be marked synthetic")
    require(all(log.get("interface") in interface_mapping for log in logs), "Every log interface must exist in interface_mapping.json")
    require(all(log.get("component") in interface_mapping[log["interface"]] for log in logs), "Every log component/interface pair must be valid")

    kpis_by_name: dict[str, list[dict]] = {}
    for row in kpis:
        kpis_by_name.setdefault(row["kpi_name"], []).append(row)
    require(set(kpis_by_name) <= set(kpi_mapping), "Every demo KPI must exist in the domain mapping")
    require(all(len(rows) == 60 for rows in kpis_by_name.values()), "Every KPI must contain 60 points")

    for incident_code, truth in truth_by_id.items():
        incident = incidents_by_id[incident_code]
        scenario = scenario_by_id[incident_code]
        scenario_id = scenario["scenario_id"]
        mapping = kpi_mapping[truth["kpi_name"]]
        expected_interfaces = set(truth["expected_interfaces"])
        expected_components = set(truth["expected_components"])
        require(expected_interfaces == set(mapping["related_interfaces"]), f"{incident_code}: interface mapping differs from ground truth")
        mapped_components = {component for name in expected_interfaces for component in interface_mapping[name]}
        require(expected_components == mapped_components, f"{incident_code}: component mapping differs from ground truth")

        series = [row for row in kpis_by_name[truth["kpi_name"]] if row["scenario_id"] == scenario_id]
        require(len(series) == 60, f"{incident_code}: KPI scenario link is incomplete")
        incident_time = timestamp(incident["incident_timestamp"])
        aligned = [row for row in series if timestamp(row["timestamp"]) == incident_time]
        require(len(aligned) == 1, f"{incident_code}: KPI anomaly must align exactly with the incident timestamp")
        require(aligned[0]["status"] == "CRITICAL", f"{incident_code}: aligned KPI point must be critical")

        expected_logs = [logs_by_id[log_id] for log_id in truth["evidence_log_ids"]]
        for log in expected_logs:
            require(log["metadata"].get("scenario_id") == scenario_id, f"{incident_code}: evidence log has the wrong scenario ID")
            require(log["interface"] in expected_interfaces, f"{incident_code}: evidence log is outside mapped interfaces")
            require(log["component"] in expected_components, f"{incident_code}: evidence log is outside mapped components")
            require(abs(timestamp(log["@timestamp"]) - incident_time) <= timedelta(minutes=5), f"{incident_code}: evidence log is outside the retrieval window")

        expected_documents = [knowledge_by_id[document_id] for document_id in truth["expected_knowledge_ids"]]
        for document in expected_documents:
            require(set(document["interfaces"]) <= expected_interfaces, f"{incident_code}: knowledge interface is unrelated")
            require(set(document["components"]) <= expected_components, f"{incident_code}: knowledge component is unrelated")

        if truth["expected_status"] == "INSUFFICIENT_EVIDENCE":
            require(not expected_logs and not expected_documents, f"{incident_code}: abstention scenario must not prescribe evidence")
            nearby = [
                log for log in logs
                if log["node"] in incident["nodes"]
                and log["interface"] in expected_interfaces
                and abs(timestamp(log["@timestamp"]) - incident_time) <= timedelta(minutes=5)
                and log.get("error_code")
                and not log["error_code"].endswith("_TRANSIENT")
            ]
            require(not nearby, f"{incident_code}: abstention window contains causal operational evidence")
        else:
            require(expected_logs, f"{incident_code}: supported scenario requires operational evidence")
            require(expected_documents, f"{incident_code}: supported scenario requires knowledge evidence")

    return {
        "logs": len(logs), "kpi_points": len(kpis), "incidents": len(incidents),
        "ground_truth": len(truths), "knowledge_documents": len(knowledge), "scenarios": len(scenarios),
    }


if __name__ == "__main__":
    counts = validate()
    print("Demo dataset validation passed: " + ", ".join(f"{name}={value}" for name, value in counts.items()))
