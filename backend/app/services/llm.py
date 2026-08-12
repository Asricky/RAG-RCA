import json
import time
import urllib.request

from ..config import settings


SYSTEM_PROMPT = """You are an AI assistant for 5G Core Network incident investigation.
Use only the supplied evidence. Never invent log events. Every diagnosis must reference evidence IDs.
Separate observation from inference. If evidence is insufficient, explicitly state it.
Return valid JSON with status, incident_summary, likely_root_cause, affected_components,
reasoning_summary, evidence_ids, recommended_actions, and evidence_strength."""


def _mock_rca(bundle: dict) -> dict:
    evidence = bundle["evidence_logs"]
    searchable = " ".join(f"{item.get('error_code', '')} {item['message']}" for item in evidence).lower()
    nodes = list(dict.fromkeys(item["node"] for item in evidence[:5]))
    ids = [item["evidence_id"] for item in evidence[: min(4, len(evidence))]]
    if not evidence:
        return {"status": "INSUFFICIENT_EVIDENCE", "incident_summary": "Tidak ada evidence pada konteks aktif.", "likely_root_cause": "Belum dapat ditentukan.", "affected_components": [], "reasoning_summary": "Perlu memperluas time window.", "evidence_ids": [], "recommended_actions": ["Perluas pencarian evidence."], "evidence_strength": "low"}
    if "pfcp" in searchable:
        cause = "Degradasi asosiasi PFCP antara SMF dan UPF menyebabkan timeout dan kegagalan pembentukan PDU session."
        actions = ["Periksa status PFCP association dan heartbeat UPF-01.", "Validasi reachability UDP/8805 antara SMF dan UPF.", "Korelasikan session yang gagal sebelum melakukan restart terkontrol."]
    elif "registration" in searchable or "ngap" in searchable:
        cause = "Timeout control-plane pada jalur AMF memicu retry dan kegagalan registrasi UE."
        actions = ["Periksa konektivitas N2 dan beban AMF.", "Korelasikan trace ID registrasi yang gagal.", "Validasi respons authentication service."]
    elif "packet" in searchable or "qos" in searchable:
        cause = "Degradasi user-plane pada UPF meningkatkan packet drop dan melanggar target QoS."
        actions = ["Periksa utilisasi interface N3/N6.", "Validasi queue dan policer QoS pada UPF.", "Bandingkan packet drop dengan baseline lima menit sebelumnya."]
    else:
        cause = "Anomali jaringan terdeteksi, tetapi hubungan kausal belum cukup kuat untuk diagnosis tunggal."
        actions = ["Perluas time window dan tambahkan log node terkait.", "Korelasikan trace dan session ID."]
    return {
        "status": "SUPPORTED" if len(evidence) >= 3 else "PARTIAL",
        "incident_summary": f"Ditemukan {len(evidence)} evidence relevan pada {', '.join(nodes[:3])}.",
        "likely_root_cause": cause,
        "affected_components": nodes,
        "reasoning_summary": f"Urutan kronologis dan korelasi pesan pada {', '.join(ids)} menunjukkan pola kegagalan yang konsisten; observasi dibatasi pada evidence yang tersedia.",
        "evidence_ids": ids,
        "recommended_actions": actions,
        "evidence_strength": "high" if len(evidence) >= 5 and evidence[0]["final_score"] > 0.7 else "medium",
    }


def generate_rca(question: str, bundle: dict) -> tuple[dict, int, str]:
    started = time.perf_counter()
    provider_used = "mock"
    result = None
    if settings.llm_provider == "ollama":
        payload = {
            "model": settings.ollama_model, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"Question: {question}\nEvidence:\n{bundle['ordered_context']}"}],
        }
        try:
            request = urllib.request.Request(f"{settings.ollama_base_url}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            raw = json.loads(urllib.request.urlopen(request, timeout=45).read())
            result = json.loads(raw["message"]["content"])
            provider_used = "ollama"
        except Exception:
            result = None
    if result is None:
        result = _mock_rca(bundle)
    valid_ids = {item["evidence_id"] for item in bundle["evidence_logs"]}
    result["evidence_ids"] = [item for item in result.get("evidence_ids", []) if item in valid_ids]
    if not result["evidence_ids"] and valid_ids:
        result = _mock_rca(bundle)
        provider_used = "mock-safe-fallback"
    return result, max(1, int((time.perf_counter() - started) * 1000)), provider_used


def provider_status() -> str:
    if settings.llm_provider != "ollama":
        return "Mock fallback"
    try:
        request = urllib.request.Request(f"{settings.ollama_base_url}/api/tags", method="GET")
        urllib.request.urlopen(request, timeout=1).read()
        return f"Healthy · {settings.ollama_model}"
    except Exception:
        return "Unavailable · mock fallback active"
