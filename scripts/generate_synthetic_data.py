"""Generate the deterministic, publication-safe 5G RCA demo dataset."""

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


random.seed(42)
root = Path(__file__).resolve().parents[1]
data_root = root / "data"
data_dir = data_root / "demo"
data_dir.mkdir(parents=True, exist_ok=True)
for private_dir in (data_root / "kpi" / "raw", data_root / "logs" / "raw", data_root / "knowledge" / "raw"):
    private_dir.mkdir(parents=True, exist_ok=True)

base = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)
nodes = [("AMF-01", "AMF"), ("AMF-02", "AMF"), ("SMF-01", "SMF"), ("SMF-02", "SMF"), ("UPF-01", "UPF"), ("UPF-02", "UPF")]
normal_messages = {
    "AMF": [
        ("NGAP heartbeat completed", "N2"),
        ("UE context release acknowledged", "N2"),
        ("Authentication response processed", "N12"),
        ("Registration accept sent", "N1"),
    ],
    "SMF": [
        ("PDU session active", "N11"),
        ("Policy association refreshed", "N7"),
        ("PFCP heartbeat response received", "N4"),
        ("Session report processed", "N4"),
    ],
    "UPF": [
        ("GTP-U tunnel packet forwarded", "N3"),
        ("QoS counter sampled", "N6"),
        ("PFCP session report sent", "N4"),
        ("N6 route health check passed", "N6"),
    ],
}

# index: node, component, interface, severity, message, error, trace, session, scenario
special = {
    31: ("UPF-01", "UPF", "N4", "WARNING", "PFCP heartbeat response delayed by 1800 ms", "PFCP_HEARTBEAT_DELAY", "trace-pfcp-001", "session-pfcp-001", "SCENARIO-01"),
    32: ("UPF-01", "UPF", "N4", "ERROR", "UPF association degraded after a missed PFCP heartbeat", "PFCP_ASSOC_DEGRADED", "trace-pfcp-001", "session-pfcp-001", "SCENARIO-01"),
    33: ("SMF-01", "SMF", "N4", "ERROR", "PFCP session establishment request timed out while waiting for UPF-01", "PFCP_TIMEOUT", "trace-pfcp-001", "session-pfcp-001", "SCENARIO-01"),
    34: ("SMF-01", "SMF", "N4", "CRITICAL", "PDU session establishment failed after the PFCP timeout", "PDU_SESSION_FAILED", "trace-pfcp-001", "session-pfcp-001", "SCENARIO-01"),
    35: ("AMF-01", "AMF", "N11", "WARNING", "N11 session create was rejected by SMF-01", "N11_REJECT", "trace-pfcp-001", "session-pfcp-001", "SCENARIO-01"),
    176: ("AMF-02", "AMF", "N1", "WARNING", "UE registration retry attempt 2 started", "REGISTRATION_RETRY", "trace-reg-002", "session-reg-002", "SCENARIO-02"),
    177: ("AMF-02", "AMF", "N12", "ERROR", "Authentication response timed out on the control-plane path", "CONTROL_PLANE_TIMEOUT", "trace-reg-002", "session-reg-002", "SCENARIO-02"),
    178: ("AMF-02", "AMF", "N1", "CRITICAL", "UE registration failed after the maximum retry count", "REGISTRATION_FAILED", "trace-reg-002", "session-reg-002", "SCENARIO-02"),
    179: ("AMF-02", "AMF", "N2", "ERROR", "NGAP UE context setup was aborted after registration failure", "NGAP_CONTEXT_FAILED", "trace-reg-002", "session-reg-002", "SCENARIO-02"),
    320: ("UPF-02", "UPF", "N3", "WARNING", "N3 packet drop increased above the established baseline", "PACKET_DROP_HIGH", "trace-upf-003", "session-upf-003", "SCENARIO-03"),
    321: ("UPF-02", "UPF", "N6", "ERROR", "QoS flow latency exceeded the configured N6 threshold", "QOS_DEGRADED", "trace-upf-003", "session-upf-003", "SCENARIO-03"),
    322: ("UPF-02", "UPF", "N6", "CRITICAL", "User-plane forwarding failure was detected on N6", "USER_PLANE_FAILURE", "trace-upf-003", "session-upf-003", "SCENARIO-03"),
    323: ("SMF-02", "SMF", "N4", "ERROR", "Session report from UPF-02 indicates sustained packet loss", "SESSION_PACKET_LOSS", "trace-upf-003", "session-upf-003", "SCENARIO-03"),
}

logs = []
for index in range(400):
    stamp = base + timedelta(seconds=index * 6)
    if index in special:
        node, component, interface, severity, message, error_code, trace_id, session_id, scenario_id = special[index]
    else:
        node, component = random.choice(nodes)
        message, interface = random.choice(normal_messages[component])
        severity = random.choices(["INFO", "WARNING", "ERROR"], weights=[88, 9, 3])[0]
        error_code = "" if severity == "INFO" else f"{component}_TRANSIENT"
        trace_id, session_id = f"trace-{index // 5:03d}", f"session-{index // 4:03d}"
        scenario_id = None
    log_id = f"LOG-{index + 1:04d}"
    logs.append({
        "log_id": log_id,
        "@timestamp": stamp.isoformat().replace("+00:00", "Z"),
        "node": node,
        "component": component,
        "interface": interface,
        "severity": severity,
        "message": message,
        "trace_id": trace_id,
        "session_id": session_id,
        "error_code": error_code,
        "container_name": component.lower(),
        "host": f"worker-{1 + index % 3:02d}",
        "metadata": {"synthetic": True, "scenario_id": scenario_id},
        "search_text": f"[{node}] [{component}] [{interface}] [{severity}] [{error_code}] {message}",
    })

(data_dir / "sample_logs.jsonl").write_text("\n".join(json.dumps(item) for item in logs) + "\n", encoding="utf-8")

incidents = [
    {"incident_code": "INC-001", "title": "PDU Session Establishment Failure", "description": "The PDU session success ratio dropped on SMF-01 while PFCP failures appeared between SMF-01 and UPF-01.", "incident_timestamp": "2026-08-12T10:03:24Z", "severity": "CRITICAL", "status": "INVESTIGATING", "source_type": "ANOMALY_FORECAST", "nodes": ["SMF-01", "UPF-01"]},
    {"incident_code": "INC-002", "title": "UE Registration Failure", "description": "The initial registration success ratio dropped on AMF-02 during authentication timeouts.", "incident_timestamp": "2026-08-12T10:17:48Z", "severity": "MAJOR", "status": "NEW", "source_type": "ANOMALY", "nodes": ["AMF-02"]},
    {"incident_code": "INC-003", "title": "User-Plane Delivery Degradation", "description": "The packet delivery success ratio dropped on UPF-02 after N3 packet loss and N6 latency increased.", "incident_timestamp": "2026-08-12T10:32:12Z", "severity": "CRITICAL", "status": "ANALYZED", "source_type": "FORECAST", "nodes": ["UPF-02", "SMF-02"]},
    {"incident_code": "INC-004", "title": "Policy Association KPI Degradation", "description": "The N7 policy association KPI dropped on SMF-02, but no causal operational error was captured.", "incident_timestamp": "2026-08-12T10:38:00Z", "severity": "MAJOR", "status": "NEW", "source_type": "ANOMALY", "nodes": ["SMF-02"]},
]
(data_dir / "sample_incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")

truth = [
    {"incident_code": "INC-001", "question": "Why did the PDU session establishment success ratio degrade on SMF-01?", "kpi_name": "PDU_SESSION_ESTABLISHMENT_SUCCESS_RATIO", "root_cause": "PFCP association degradation between SMF-01 and UPF-01", "evidence_log_ids": ["LOG-0032", "LOG-0033", "LOG-0034", "LOG-0035", "LOG-0036"], "expected_interfaces": ["N4", "N11"], "expected_components": ["AMF", "SMF", "UPF"], "expected_knowledge_ids": ["KB-PFCP-001"], "expected_status": "SUPPORTED", "notes": "Synthetic Scenario 01"},
    {"incident_code": "INC-002", "question": "What caused the initial registration KPI degradation?", "kpi_name": "INITIAL_REGISTRATION_SUCCESS_RATIO", "root_cause": "Authentication response timeout on the AMF control-plane path", "evidence_log_ids": ["LOG-0177", "LOG-0178", "LOG-0179", "LOG-0180"], "expected_interfaces": ["N1", "N2", "N8", "N12"], "expected_components": ["AMF", "AUSF", "GNB", "UDM", "UE"], "expected_knowledge_ids": ["KB-REG-001"], "expected_status": "SUPPORTED", "notes": "Synthetic Scenario 02"},
    {"incident_code": "INC-003", "question": "What caused the user-plane delivery KPI degradation?", "kpi_name": "USER_PLANE_PACKET_DELIVERY_SUCCESS_RATIO", "root_cause": "Packet loss and QoS degradation across the N3 and N6 paths", "evidence_log_ids": ["LOG-0321", "LOG-0322", "LOG-0323", "LOG-0324"], "expected_interfaces": ["N3", "N4", "N6"], "expected_components": ["DATA_NETWORK", "GNB", "SMF", "UPF"], "expected_knowledge_ids": ["KB-UPF-001"], "expected_status": "SUPPORTED", "notes": "Synthetic Scenario 03"},
    {"incident_code": "INC-004", "question": "What caused the N7 policy association KPI degradation?", "kpi_name": "N7_POLICY_ASSOCIATION_SUCCESS_RATIO", "root_cause": "Insufficient operational evidence", "evidence_log_ids": [], "expected_interfaces": ["N7"], "expected_components": ["PCF", "SMF"], "expected_knowledge_ids": [], "expected_status": "INSUFFICIENT_EVIDENCE", "notes": "Synthetic insufficient-evidence scenario"},
]
(data_dir / "sample_ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")

knowledge = [
    {
        "document_id": "KB-PFCP-001", "title": "N4 PFCP Association Recovery Runbook", "document_type": "RUNBOOK", "source": "Synthetic NOC knowledge base", "version": "1.0",
        "interfaces": ["N4"], "components": ["SMF", "UPF"], "error_codes": ["PFCP_HEARTBEAT_DELAY", "PFCP_ASSOC_DEGRADED", "PFCP_TIMEOUT", "PDU_SESSION_FAILED"],
        "symptoms": ["missed PFCP heartbeat", "PFCP request timeout", "PDU session establishment failure"],
        "content": "Use this runbook when N4 PFCP heartbeat loss is followed by association degradation and PDU session establishment failures.",
        "investigation_steps": ["Verify N4 reachability and UDP port 8805 between the affected SMF and UPF.", "Check PFCP heartbeat and association state on both network functions.", "Correlate the affected trace and session identifiers before changing service state."],
        "resolution_steps": ["Restore the N4 transport path if reachability is impaired.", "Re-establish the PFCP association using the approved maintenance procedure after connectivity is stable.", "Confirm that the PDU session success ratio returns to baseline."],
        "recommended_action": "Restore N4 connectivity, re-establish the PFCP association under the approved procedure, and verify KPI recovery.",
        "metadata": {"synthetic": True, "scenario_id": "SCENARIO-01"},
    },
    {
        "document_id": "KB-REG-001", "title": "Initial Registration Timeout Troubleshooting Guide", "document_type": "TROUBLESHOOTING_GUIDE", "source": "Synthetic NOC knowledge base", "version": "1.0",
        "interfaces": ["N1", "N2", "N8", "N12"], "components": ["AMF", "AUSF", "UDM"], "error_codes": ["REGISTRATION_RETRY", "CONTROL_PLANE_TIMEOUT", "REGISTRATION_FAILED", "NGAP_CONTEXT_FAILED"],
        "symptoms": ["authentication timeout", "registration retry", "NGAP context abort"],
        "content": "Use this guide when UE registration failures follow authentication response timeouts and repeated retries.",
        "investigation_steps": ["Correlate the UE registration trace across N1, N2, and N12.", "Verify AUSF and UDM response latency.", "Check AMF saturation and timeout counters."],
        "resolution_steps": ["Restore the delayed authentication dependency.", "Retry registration only after the dependency is healthy.", "Verify registration success ratio recovery."],
        "recommended_action": "Restore the delayed authentication path and confirm successful registration on a controlled test UE.",
        "metadata": {"synthetic": True, "scenario_id": "SCENARIO-02"},
    },
    {
        "document_id": "KB-UPF-001", "title": "N3 and N6 User-Plane Packet Loss Runbook", "document_type": "RUNBOOK", "source": "Synthetic NOC knowledge base", "version": "1.0",
        "interfaces": ["N3", "N4", "N6"], "components": ["SMF", "UPF"], "error_codes": ["PACKET_DROP_HIGH", "QOS_DEGRADED", "USER_PLANE_FAILURE", "SESSION_PACKET_LOSS"],
        "symptoms": ["packet drop", "QoS latency", "user-plane forwarding failure"],
        "content": "Use this runbook when packet loss on N3 or N6 coincides with UPF forwarding and QoS failures.",
        "investigation_steps": ["Inspect N3 and N6 interface counters and queue drops.", "Validate UPF QoS policy and resource utilization.", "Correlate the SMF session report with the affected UPF."],
        "resolution_steps": ["Remove the confirmed transport or queue bottleneck.", "Restore the approved QoS policy if it drifted.", "Confirm packet delivery and latency KPI recovery."],
        "recommended_action": "Correct the confirmed N3/N6 transport or QoS bottleneck and verify user-plane KPI recovery.",
        "metadata": {"synthetic": True, "scenario_id": "SCENARIO-03"},
    },
]
(data_dir / "sample_knowledge.json").write_text(json.dumps(knowledge, indent=2), encoding="utf-8")


def kpi_series(*, scenario_id: str, kpi_name: str, node: str, incident_time: datetime, baseline: float, threshold: float, minimum: float, interfaces: list[str], components: list[str]) -> list[dict]:
    rows = []
    start = incident_time - timedelta(seconds=34 * 6)
    drop = baseline - minimum
    for index in range(60):
        stamp = start + timedelta(seconds=index * 6)
        distance = abs(index - 34)
        degraded = distance <= 4
        if degraded:
            severity_factor = max(0, 5 - distance) / 5
            value = round(baseline - drop * severity_factor, 2)
            anomaly_score = round(max(0.02, 0.94 - distance * 0.16), 2)
            forecast = round(value - max(0.5, drop * 0.08), 2)
        else:
            value = round(baseline - 0.15 + random.random() * 0.25, 2)
            anomaly_score = round(0.02 + random.random() * 0.03, 2)
            forecast = round(baseline - 0.1 + random.random() * 0.2, 2)
        rows.append({
            "scenario_id": scenario_id,
            "timestamp": stamp.isoformat().replace("+00:00", "Z"),
            "kpi_name": kpi_name,
            "kpi_level": "L1" if scenario_id != "SCENARIO-02" else "L2",
            "node": node,
            "value": value,
            "baseline_value": baseline,
            "anomaly_score": anomaly_score,
            "forecast_value": forecast,
            "threshold": threshold,
            "status": "CRITICAL" if anomaly_score >= 0.75 else "NORMAL",
            "related_interfaces": ";".join(interfaces),
            "related_components": ";".join(components),
        })
    return rows


kpi_rows = [
    *kpi_series(scenario_id="SCENARIO-01", kpi_name="PDU_SESSION_ESTABLISHMENT_SUCCESS_RATIO", node="SMF-01", incident_time=datetime(2026, 8, 12, 10, 3, 24, tzinfo=timezone.utc), baseline=99.5, threshold=95.0, minimum=82.7, interfaces=["N4", "N11"], components=["AMF", "SMF", "UPF"]),
    *kpi_series(scenario_id="SCENARIO-02", kpi_name="INITIAL_REGISTRATION_SUCCESS_RATIO", node="AMF-02", incident_time=datetime(2026, 8, 12, 10, 17, 48, tzinfo=timezone.utc), baseline=98.8, threshold=92.0, minimum=76.0, interfaces=["N1", "N2", "N8", "N12"], components=["AMF", "AUSF", "GNB", "UDM", "UE"]),
    *kpi_series(scenario_id="SCENARIO-03", kpi_name="USER_PLANE_PACKET_DELIVERY_SUCCESS_RATIO", node="UPF-02", incident_time=datetime(2026, 8, 12, 10, 32, 12, tzinfo=timezone.utc), baseline=99.2, threshold=94.0, minimum=81.0, interfaces=["N3", "N4", "N6"], components=["DATA_NETWORK", "GNB", "SMF", "UPF"]),
    *kpi_series(scenario_id="SCENARIO-04", kpi_name="N7_POLICY_ASSOCIATION_SUCCESS_RATIO", node="SMF-02", incident_time=datetime(2026, 8, 12, 10, 38, 0, tzinfo=timezone.utc), baseline=99.0, threshold=93.0, minimum=84.0, interfaces=["N7"], components=["PCF", "SMF"]),
]
with (data_dir / "sample_kpi.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(kpi_rows[0]))
    writer.writeheader()
    writer.writerows(kpi_rows)

scenarios = [
    {"scenario_id": f"SCENARIO-{index:02d}", **item}
    for index, item in enumerate(truth, 1)
]
(data_dir / "sample_scenarios.json").write_text(json.dumps(scenarios, indent=2), encoding="utf-8")

print(
    f"Generated {len(logs)} logs, {len(kpi_rows)} KPI points, {len(incidents)} incidents, "
    f"{len(knowledge)} knowledge documents, and {len(truth)} ground-truth scenarios"
)
