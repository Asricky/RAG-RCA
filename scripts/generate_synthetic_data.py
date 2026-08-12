"""Generate a deterministic, customer-safe 5G Core demo dataset."""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


random.seed(42)
root = Path(__file__).resolve().parents[1]
data_dir = root / "data"
data_dir.mkdir(exist_ok=True)
base = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)
nodes = [("AMF-01", "AMF"), ("AMF-02", "AMF"), ("SMF-01", "SMF"), ("SMF-02", "SMF"), ("UPF-01", "UPF"), ("UPF-02", "UPF")]
normal_messages = {
    "AMF": ["NGAP heartbeat completed", "UE context release acknowledged", "Authentication response processed", "Registration accept sent"],
    "SMF": ["PDU session active", "Policy association refreshed", "PFCP heartbeat response received", "Session report processed"],
    "UPF": ["GTP-U tunnel packet forwarded", "QoS counter sampled", "PFCP session report sent", "N6 route health check passed"],
}
special = {
    31: ("UPF-01", "UPF", "WARNING", "PFCP heartbeat response delayed by 1800ms", "PFCP_HEARTBEAT_DELAY", "trace-pfcp-001", "session-pfcp-001"),
    32: ("UPF-01", "UPF", "ERROR", "UPF association degradation detected after missed PFCP heartbeat", "PFCP_ASSOC_DEGRADED", "trace-pfcp-001", "session-pfcp-001"),
    33: ("SMF-01", "SMF", "ERROR", "PFCP request timed out waiting for UPF-01", "PFCP_TIMEOUT", "trace-pfcp-001", "session-pfcp-001"),
    34: ("SMF-01", "SMF", "CRITICAL", "PDU session establishment failed after PFCP timeout", "PDU_SESSION_FAILED", "trace-pfcp-001", "session-pfcp-001"),
    35: ("AMF-01", "AMF", "WARNING", "N11 session create rejected by SMF-01", "N11_REJECT", "trace-pfcp-001", "session-pfcp-001"),
    176: ("AMF-02", "AMF", "WARNING", "UE registration retry attempt 2", "REGISTRATION_RETRY", "trace-reg-002", "session-reg-002"),
    177: ("AMF-02", "AMF", "ERROR", "Control-plane response timeout during authentication", "CONTROL_PLANE_TIMEOUT", "trace-reg-002", "session-reg-002"),
    178: ("AMF-02", "AMF", "CRITICAL", "UE registration failed after maximum retry count", "REGISTRATION_FAILED", "trace-reg-002", "session-reg-002"),
    179: ("AMF-02", "AMF", "ERROR", "NGAP UE context setup aborted", "NGAP_CONTEXT_FAILED", "trace-reg-002", "session-reg-002"),
    320: ("UPF-02", "UPF", "WARNING", "N3 packet drop increased above baseline", "PACKET_DROP_HIGH", "trace-upf-003", "session-upf-003"),
    321: ("UPF-02", "UPF", "ERROR", "QoS flow latency exceeded configured threshold", "QOS_DEGRADED", "trace-upf-003", "session-upf-003"),
    322: ("UPF-02", "UPF", "CRITICAL", "User-plane forwarding failure detected on N6", "USER_PLANE_FAILURE", "trace-upf-003", "session-upf-003"),
    323: ("SMF-02", "SMF", "ERROR", "Session report indicates UPF-02 packet loss", "SESSION_PACKET_LOSS", "trace-upf-003", "session-upf-003"),
}

logs = []
for index in range(400):
    stamp = base + timedelta(seconds=index * 6)
    if index in special:
        node, component, severity, message, error_code, trace_id, session_id = special[index]
    else:
        node, component = random.choice(nodes)
        severity = random.choices(["INFO", "WARNING", "ERROR"], weights=[88, 9, 3])[0]
        message = random.choice(normal_messages[component])
        error_code = "" if severity == "INFO" else f"{component}_TRANSIENT"
        trace_id, session_id = f"trace-{index // 5:03d}", f"session-{index // 4:03d}"
    log_id = f"LOG-{index + 1:04d}"
    logs.append({
        "log_id": log_id, "@timestamp": stamp.isoformat().replace("+00:00", "Z"), "node": node, "component": component,
        "severity": severity, "message": message, "trace_id": trace_id, "session_id": session_id,
        "error_code": error_code, "container_name": component.lower(), "host": f"worker-{1 + index % 3:02d}", "metadata": {"synthetic": True},
        "search_text": f"[{node}] [{severity}] [{error_code}] {message}",
    })

(data_dir / "sample_logs.jsonl").write_text("\n".join(json.dumps(item) for item in logs) + "\n", encoding="utf-8")
incidents = [
    {"incident_code": "INC-001", "title": "PDU Session Establishment Failure", "description": "Spike kegagalan session pada SMF-01 yang berkorelasi dengan UPF-01.", "incident_timestamp": "2026-08-12T10:03:24Z", "severity": "CRITICAL", "status": "INVESTIGATING", "source_type": "ANOMALY", "nodes": ["SMF-01", "UPF-01"]},
    {"incident_code": "INC-002", "title": "UE Registration Failure", "description": "Peningkatan retry dan timeout registrasi pada AMF-02.", "incident_timestamp": "2026-08-12T10:17:48Z", "severity": "MAJOR", "status": "NEW", "source_type": "ANOMALY", "nodes": ["AMF-02"]},
    {"incident_code": "INC-003", "title": "User Plane QoS Degradation", "description": "Packet drop dan latency tinggi pada UPF-02.", "incident_timestamp": "2026-08-12T10:32:12Z", "severity": "CRITICAL", "status": "ANALYZED", "source_type": "FORECAST", "nodes": ["UPF-02", "SMF-02"]},
]
(data_dir / "sample_incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
truth = [
    {"incident_code": "INC-001", "root_cause": "PFCP association degradation between SMF-01 and UPF-01", "evidence_log_ids": ["LOG-0032", "LOG-0033", "LOG-0034", "LOG-0035", "LOG-0036"], "notes": "Synthetic scenario 1"},
    {"incident_code": "INC-002", "root_cause": "AMF control-plane timeout causing UE registration failure", "evidence_log_ids": ["LOG-0177", "LOG-0178", "LOG-0179", "LOG-0180"], "notes": "Synthetic scenario 2"},
    {"incident_code": "INC-003", "root_cause": "UPF packet drop and QoS degradation", "evidence_log_ids": ["LOG-0321", "LOG-0322", "LOG-0323", "LOG-0324"], "notes": "Synthetic scenario 3"},
]
(data_dir / "sample_ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
print(f"Generated {len(logs)} logs, {len(incidents)} incidents, and {len(truth)} ground-truth cases")

