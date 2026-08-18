"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowPathIcon, ChevronDownIcon, PaperAirplaneIcon, SparklesIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt } from "@/lib/api";

type EvidenceLog = {
  log_id: string; "@timestamp": string; node: string; severity: string; message: string;
  evidence_id?: string; bm25_score?: number; semantic_score?: number; final_score?: number;
  [key: string]: unknown;
};

export type KPIContext = {
  kpi_name: string; kpi_level?: string | null; node: string; timestamp?: string;
  current_value: number; baseline_value?: number | null; anomaly_score?: number | null;
  forecast_value?: number | null; threshold?: number | null; status?: string;
  related_interfaces?: string[]; related_components?: string[];
};

function logEvidence(bundle: any): EvidenceLog[] {
  return bundle?.log_evidence || bundle?.evidence_logs || [];
}

export default function AssistantPanel({ selected, filters, kpiContext, onEvidence, open, onClose, analyzeRequest = 0 }: {
  selected: EvidenceLog[];
  filters: { severity: string; keyword: string };
  kpiContext?: KPIContext | null;
  onEvidence: (log: EvidenceLog) => void;
  open: boolean;
  onClose: () => void;
  analyzeRequest?: number;
}) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [details, setDetails] = useState(false);
  const [conversation, setConversation] = useState<string>();
  const [error, setError] = useState("");
  const handledRequest = useRef(0);

  useEffect(() => {
    if (analyzeRequest > 0 && analyzeRequest !== handledRequest.current) {
      handledRequest.current = analyzeRequest;
      const prompt = selected.length === 1
        ? "Analyze the selected log and explain the most likely root cause."
        : `Analyze the ${selected.length} selected logs, explain their correlation, and identify the most likely root cause.`;
      void ask(undefined, prompt);
    }
  }, [analyzeRequest]);

  async function ask(event?: FormEvent, suggestedQuestion?: string) {
    event?.preventDefault();
    const prompt = (suggestedQuestion || question).trim();
    if (!prompt || loading) return;
    setQuestion("");
    setLoading(true);
    setError("");
    try {
      const data = await api<any>("/analysis/run", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: conversation,
          question: prompt,
          ui_context: {
            selected_log_ids: selected.map((log) => log.log_id),
            selected_nodes: [...new Set(selected.map((log) => log.node))],
            severity: filters.severity ? [filters.severity] : [],
            keyword: filters.keyword || null,
            incident_timestamp: kpiContext?.timestamp || null,
            kpi_context: kpiContext || null,
            related_interfaces: kpiContext?.related_interfaces || [],
            related_components: kpiContext?.related_components || [],
          },
          retrieval_config: { alpha: 0.5, top_k: 10 },
        }),
      });
      setResult({ ...data, question: prompt });
      setConversation(data.conversation_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The analysis could not be completed");
    } finally { setLoading(false); }
  }

  async function expand() {
    if (!result || loading) return;
    setLoading(true);
    setError("");
    try {
      const data = await api<any>(`/analysis/${result.analysis_id}/expand-evidence`, { method: "POST" });
      setResult({ ...data, question: result.question });
      setConversation(data.conversation_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The evidence search could not be expanded");
    } finally { setLoading(false); }
  }

  const suggestedPrompts = [
    "What happened during this period?",
    "What is the most likely root cause?",
    "Which logs provide the strongest evidence?",
    "Which interface appears to be affected?",
    "What resolution does the knowledge base recommend?",
  ];
  const bundle = result?.evidence_bundle;
  const rca = result?.rca_result;

  return <aside className={open ? "assistant mobile-open" : "assistant"} aria-label="AI RCA Assistant">
    <div className="assistant-head"><div className="ai-orb"><SparklesIcon /></div><div><h3>AI RCA Assistant</h3><span><i />Evidence-grounded</span></div><button className="assistant-close" aria-label="Close AI assistant" onClick={onClose}><XMarkIcon /></button></div>
    <div className="context-card"><b>Active context</b><div><span>{kpiContext?.kpi_name?.replaceAll("_", " ") || (selected.length ? `${selected.length} selected logs` : "Live monitoring window")}</span><span>{selected.length ? [...new Set(selected.map((log) => log.node))].join(", ") : kpiContext?.node || "All network functions"}</span></div></div>
    <div className="chat-scroll" aria-live="polite">
      {error && <div className="assistant-error" role="alert">{error}</div>}
      {!result && !loading && <><div className="ai-welcome"><SparklesIcon /><h4>Ready to investigate</h4><p>Select logs or ask about the active KPI and network context.</p></div><div className="suggestions">
        {suggestedPrompts.map((prompt) => <button key={prompt} onClick={() => ask(undefined, prompt)}>{prompt}</button>)}
      </div></>}
      {loading && <div className="analysis-progress"><div className="spinner" /><b>Running hybrid retrieval</b><span>Filtering candidates · BM25 · semantic search</span></div>}
      {result && !loading && <><div className="user-bubble">{result.question}</div><div className="rca-card">
        <div className="rca-title"><SparklesIcon />RCA RESULT <span className={`strength ${String(rca.evidence_strength).toLowerCase()}`}>{rca.evidence_strength}</span></div>
        <ResultSection label="Incident summary"><p>{rca.incident_summary}</p></ResultSection>
        <ResultSection label="Likely root cause" className="cause"><p>{rca.likely_root_cause}</p></ResultSection>
        <ResultSection label="Affected components"><div className="chips">{rca.affected_components.map((item: string) => <span key={item}>{item}</span>)}</div></ResultSection>
        {(rca.affected_interfaces || []).length > 0 && <ResultSection label="Affected interfaces"><div className="chips">{rca.affected_interfaces.map((item: string) => <span key={item}>{item}</span>)}</div></ResultSection>}
        <ResultSection label="Reasoning"><p>{rca.reasoning_summary}</p></ResultSection>
        {(bundle.kpi_evidence || []).length > 0 && <ResultSection label="KPI evidence"><div className="evidence-list">{bundle.kpi_evidence.map((item: any) => <div className="evidence-static" key={item.evidence_id}><b>[{item.evidence_id}] {String(item.kpi_name).replaceAll("_", " ")}</b><span>{item.value} · baseline {item.baseline ?? "n/a"} · anomaly {item.anomaly_score ?? "n/a"}</span></div>)}</div></ResultSection>}
        {(bundle.topology_evidence || []).length > 0 && <ResultSection label="Topology evidence"><div className="evidence-list">{bundle.topology_evidence.map((item: any) => <div className="evidence-static" key={item.evidence_id}><b>[{item.evidence_id}] {item.interface}</b><span>{item.components.join(" · ")}</span></div>)}</div></ResultSection>}
        {logEvidence(bundle).length > 0 && <ResultSection label="Evidence score visualization"><EvidenceScoreChart evidence={logEvidence(bundle)} /></ResultSection>}
        <ResultSection label="Supporting log evidence"><div className="evidence-list">{logEvidence(bundle).filter((log) => rca.evidence_ids.includes(log.evidence_id)).map((log) => <button key={log.log_id} onClick={() => onEvidence(log)}><b>[{log.evidence_id}] {log.node} · {log.severity} · {fmt(log["@timestamp"])}</b><span>{log.message}</span></button>)}</div></ResultSection>
        {(bundle.knowledge_evidence || []).length > 0 && <ResultSection label="Knowledge sources"><div className="evidence-list">{bundle.knowledge_evidence.map((item: any) => <div className="evidence-static" key={item.evidence_id}><b>[{item.evidence_id}] {item.title}</b><span>{item.document_type} · {item.source}</span></div>)}</div></ResultSection>}
        <ResultSection label="Recommended investigation"><ol>{(rca.recommended_investigation || rca.recommended_actions || []).map((item: string) => <li key={item}>{item}</li>)}</ol></ResultSection>
        {(rca.suggested_resolution || []).length > 0 && <ResultSection label="Suggested resolution"><ol>{rca.suggested_resolution.map((item: any) => <li key={item.action}>{item.action} <small>{item.knowledge_sources.join(", ")}</small></li>)}</ol></ResultSection>}
        <button className="details-btn" onClick={() => setDetails(!details)} aria-expanded={details}>View Retrieval Details <ChevronDownIcon /></button>
        {details && <RetrievalDetails bundle={bundle} />}
        <button className="expand-btn" onClick={expand}><ArrowPathIcon />Search More Evidence</button>
      </div></>}
    </div>
    <form className="chat-input" onSubmit={ask}><textarea maxLength={2000} aria-label="Ask AI about the active incident" placeholder="Ask about the active KPI, incident, or logs..." value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(); } }} /><button aria-label="Send question" disabled={loading || !question.trim()}><PaperAirplaneIcon /></button><small>English questions only · Responses cite source evidence · Enter to send</small></form>
  </aside>;
}

function ResultSection({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return <section className={className}><label>{label}</label>{children}</section>;
}

function RetrievalDetails({ bundle }: { bundle: any }) {
  const context = bundle.incident_context || {};
  return <div className="retrieval"><div><span>KPI<b>{context.kpi_context?.kpi_name?.replaceAll("_", " ") || "None"}</b></span><span>Interfaces<b>{(context.related_interfaces || []).join(", ") || "None"}</b></span><span>Components<b>{(context.related_components || []).join(", ") || "None"}</b></span><span>Candidates<b>{bundle.candidate_count}</b></span><span>Alpha<b>{bundle.retrieval_config.alpha}</b></span><span>Top-K<b>{bundle.retrieval_config.top_k}</b></span><span>Latency<b>{bundle.retrieval_latency_ms} ms</b></span></div><table><thead><tr><th>Evidence</th><th>BM25</th><th>Semantic</th><th>Final</th></tr></thead><tbody>{logEvidence(bundle).map((log) => <tr key={log.log_id}><td>{log.evidence_id}</td><td>{log.bm25_score}</td><td>{log.semantic_score}</td><td><b>{log.final_score}</b></td></tr>)}</tbody></table></div>;
}

function EvidenceScoreChart({ evidence }: { evidence: EvidenceLog[] }) {
  const data = evidence.slice(0, 8).map((log) => ({
    evidence: log.evidence_id,
    BM25: Math.round(Number(log.bm25_score || 0) * 100),
    Semantic: Math.round(Number(log.semantic_score || 0) * 100),
    Final: Math.round(Number(log.final_score || 0) * 100),
  }));
  return <div className="rca-chart" role="img" aria-label="Comparison of BM25, semantic, and final evidence scores">
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 12, right: 4, left: -25, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#233044" /><XAxis dataKey="evidence" stroke="#718096" fontSize={8} /><YAxis domain={[0, 100]} stroke="#718096" fontSize={8} />
        <Tooltip contentStyle={{ background: "#101827", border: "1px solid #29364a", borderRadius: 7, fontSize: 9 }} /><Legend wrapperStyle={{ fontSize: 8 }} />
        <Bar dataKey="BM25" fill="#34d5c5" radius={[2, 2, 0, 0]} /><Bar dataKey="Semantic" fill="#9b87f5" radius={[2, 2, 0, 0]} /><Bar dataKey="Final" fill="#f6b94a" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
    <small>Normalized scores (%) for the top {data.length} log evidence items.</small>
  </div>;
}
