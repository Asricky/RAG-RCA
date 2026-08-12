"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowPathIcon, ChevronDownIcon, PaperAirplaneIcon, SparklesIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { api, fmt } from "@/lib/api";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type EvidenceLog = {
  log_id: string; "@timestamp": string; node: string; severity: string; message: string;
  evidence_id?: string; bm25_score?: number; semantic_score?: number; final_score?: number;
  [key: string]: unknown;
};

export default function AssistantPanel({ selected, filters, onEvidence, open, onClose, analyzeRequest = 0 }: {
  selected: EvidenceLog[];
  filters: { severity: string; keyword: string };
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
      void ask(undefined, selected.length === 1 ? "Analisis log terpilih dan jelaskan kemungkinan root cause." : `Analisis ${selected.length} log terpilih, jelaskan korelasinya, dan tentukan kemungkinan root cause.`);
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
          },
          retrieval_config: { alpha: 0.5, top_k: 10 },
        }),
      });
      setResult({ ...data, question: prompt });
      setConversation(data.conversation_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analisis gagal dijalankan");
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
      setError(caught instanceof Error ? caught.message : "Evidence gagal diperluas");
    } finally { setLoading(false); }
  }

  return <aside className={open ? "assistant mobile-open" : "assistant"} aria-label="AI RCA Assistant">
    <div className="assistant-head"><div className="ai-orb"><SparklesIcon /></div><div><h3>AI RCA Assistant</h3><span><i />Evidence-grounded</span></div><button className="assistant-close" aria-label="Close AI assistant" onClick={onClose}><XMarkIcon /></button></div>
    <div className="context-card"><b>Active context</b><div><span>{selected.length ? `${selected.length} selected logs` : "Live monitoring window"}</span><span>{selected.length ? [...new Set(selected.map((log) => log.node))].join(", ") : "All network functions"}</span></div></div>
    <div className="chat-scroll" aria-live="polite">
      {error && <div className="assistant-error" role="alert">{error}</div>}
      {!result && !loading && <><div className="ai-welcome"><SparklesIcon /><h4>Ready to investigate</h4><p>Pilih log atau tanyakan tentang kondisi jaringan saat ini.</p></div><div className="suggestions">
        {["Apa yang terjadi pada periode ini?", "Apa kemungkinan root cause?", "Apakah ada hubungan SMF dan UPF?"].map((prompt) => <button key={prompt} onClick={() => ask(undefined, prompt)}>{prompt}</button>)}
      </div></>}
      {loading && <div className="analysis-progress"><div className="spinner" /><b>Running hybrid retrieval</b><span>Filtering candidates · BM25 · semantic search</span></div>}
      {result && !loading && <><div className="user-bubble">{result.question}</div><div className="rca-card">
        <div className="rca-title"><SparklesIcon />RCA RESULT <span className={`strength ${result.rca_result.evidence_strength}`}>{result.rca_result.evidence_strength}</span></div>
        <ResultSection label="Incident summary"><p>{result.rca_result.incident_summary}</p></ResultSection>
        <ResultSection label="Likely root cause" className="cause"><p>{result.rca_result.likely_root_cause}</p></ResultSection>
        <ResultSection label="Affected components"><div className="chips">{result.rca_result.affected_components.map((item: string) => <span key={item}>{item}</span>)}</div></ResultSection>
        <ResultSection label="Reasoning"><p>{result.rca_result.reasoning_summary}</p></ResultSection>
        <ResultSection label="Evidence score visualization"><EvidenceScoreChart evidence={result.evidence_bundle.evidence_logs} /></ResultSection>
        <ResultSection label="Supporting evidence"><div className="evidence-list">{result.evidence_bundle.evidence_logs.filter((log: EvidenceLog) => result.rca_result.evidence_ids.includes(log.evidence_id)).map((log: EvidenceLog) => <button key={log.log_id} onClick={() => onEvidence(log)}><b>[{log.evidence_id}] {log.node} · {log.severity} · {fmt(log["@timestamp"])}</b><span>{log.message}</span></button>)}</div></ResultSection>
        <ResultSection label="Recommended actions"><ol>{result.rca_result.recommended_actions.map((item: string) => <li key={item}>{item}</li>)}</ol></ResultSection>
        <button className="details-btn" onClick={() => setDetails(!details)} aria-expanded={details}>View Retrieval Details <ChevronDownIcon /></button>
        {details && <RetrievalDetails bundle={result.evidence_bundle} />}
        <button className="expand-btn" onClick={expand}><ArrowPathIcon />Search More Evidence</button>
      </div></>}
    </div>
    <form className="chat-input" onSubmit={ask}><textarea maxLength={2000} aria-label="Ask AI about logs" placeholder="Ask about current logs..." value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(); } }} /><button aria-label="Send question" disabled={loading || !question.trim()}><PaperAirplaneIcon /></button><small>Responses cite source evidence · Enter to send</small></form>
  </aside>;
}

function ResultSection({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return <section className={className}><label>{label}</label>{children}</section>;
}

function RetrievalDetails({ bundle }: { bundle: any }) {
  return <div className="retrieval"><div><span>Candidates<b>{bundle.candidate_count}</b></span><span>Alpha<b>{bundle.retrieval_config.alpha}</b></span><span>Top-K<b>{bundle.retrieval_config.top_k}</b></span><span>Latency<b>{bundle.retrieval_latency_ms} ms</b></span></div><table><thead><tr><th>Evidence</th><th>BM25</th><th>Semantic</th><th>Final</th></tr></thead><tbody>{bundle.evidence_logs.map((log: EvidenceLog) => <tr key={log.log_id}><td>{log.evidence_id}</td><td>{log.bm25_score}</td><td>{log.semantic_score}</td><td><b>{log.final_score}</b></td></tr>)}</tbody></table></div>;
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
    <small>Normalized score (%) untuk Top-{data.length} evidence.</small>
  </div>;
}
