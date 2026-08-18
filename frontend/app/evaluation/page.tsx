"use client";

import { useEffect, useState } from "react";
import { ArrowPathIcon, BeakerIcon, PlayIcon } from "@heroicons/react/24/outline";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

export default function Evaluation() {
  const [runs, setRuns] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [alpha, setAlpha] = useState(0.5);
  const [topK, setTopK] = useState(10);
  const [windowMinutes, setWindowMinutes] = useState(5);
  const [embedding, setEmbedding] = useState({ model: "sentence-transformers/all-MiniLM-L6-v2", dimension: 384 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      const [runRows, datasetRows, embeddingInfo] = await Promise.all([
        api<any[]>("/evaluation"), api<any[]>("/datasets"), api<any>("/health/embedding"),
      ]);
      setRuns(runRows);
      setDatasets(datasetRows);
      setEmbedding(embeddingInfo);
      if (!datasetId && datasetRows[0]) setDatasetId(datasetRows[0].id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Evaluation data could not be loaded");
    }
  }

  useEffect(() => { void load(); }, []);

  async function run() {
    setLoading(true);
    setError("");
    try {
      await api("/evaluation/run", {
        method: "POST",
        body: JSON.stringify({
          name: `Hybrid benchmark alpha=${alpha}`,
          dataset_id: datasetId || null,
          alpha,
          top_k: topK,
          time_before_minutes: windowMinutes,
          time_after_minutes: windowMinutes,
        }),
      });
      setMessage("The evaluation completed successfully.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  const latest = runs[0]?.metrics;
  return <AppShell title="Evaluation Lab" subtitle="Measure hybrid retrieval quality against ground truth" actions={<button className="icon-btn" aria-label="Refresh evaluations" onClick={() => void load()}><ArrowPathIcon /></button>}>
    <div className="page-content">
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => void load()}>Retry</button></div>}
      {message && <div className="success-banner"><span>{message}</span><button onClick={() => setMessage("")}>Dismiss</button></div>}
      <div className="eval-layout">
        <section className="eval-config panel">
          <div className="panel-title"><BeakerIcon /><div><h3>Retrieval experiment</h3><p>OpenSearch BM25 + Sentence Transformer kNN</p></div></div>
          <label>Dataset<select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>{datasets.length ? datasets.map((item) => <option value={item.id} key={item.id}>{item.name}</option>) : <option value="">No datasets available</option>}</select></label>
          <label>BM25 weight (alpha)<div className="range"><input type="range" min="0" max="1" step=".1" value={alpha} onChange={(event) => setAlpha(+event.target.value)} /><b>{alpha.toFixed(1)}</b></div></label>
          <label>Top-K<select value={topK} onChange={(event) => setTopK(+event.target.value)}><option value={5}>5 evidence</option><option value={10}>10 evidence</option><option value={20}>20 evidence</option></select></label>
          <label>Time window<select value={windowMinutes} onChange={(event) => setWindowMinutes(+event.target.value)}>{[1, 5, 10, 15, 30].map((value) => <option value={value} key={value}>+/- {value} minutes</option>)}</select></label>
          <label>Indexed embedding model<select value={embedding.model} disabled><option value={embedding.model}>{embedding.model.split("/").pop()} / {embedding.dimension} dimensions</option></select></label>
          <button className="primary-btn" onClick={() => void run()} disabled={loading || !datasetId}><PlayIcon />{loading ? "Running benchmark..." : "Run evaluation"}</button>
        </section>
        <section className="eval-results">
          <div className="metric-grid">{latest ? <>
            <EvalMetric label="Precision@K" value={latest.precision_at_k} />
            <EvalMetric label="Recall@K" value={latest.recall_at_k} />
            <EvalMetric label="Knowledge Hit Rate" value={latest.knowledge_hit_rate || 0} />
            <EvalMetric label="Interface Recall" value={latest.interface_recall || 0} />
          </> : <div className="empty-state"><BeakerIcon /><h3>No evaluation runs yet</h3><p>Run the synthetic benchmark to calculate retrieval metrics.</p></div>}</div>
          <div className="panel"><h3>Experiment history</h3><div className="table-wrap"><table className="data-table">
            <thead><tr><th>Name</th><th>Alpha</th><th>Top-K</th><th>Precision</th><th>Recall</th><th>Knowledge</th><th>Interfaces</th><th>Latency</th></tr></thead>
            <tbody>{runs.map((item) => <tr key={item.id}><td><b>{item.name}</b></td><td>{item.alpha}</td><td>{item.top_k}</td><td>{item.metrics.precision_at_k}</td><td>{item.metrics.recall_at_k}</td><td>{item.metrics.knowledge_hit_rate ?? "n/a"}</td><td>{item.metrics.interface_recall ?? "n/a"}</td><td>{item.metrics.retrieval_latency_ms} ms</td></tr>)}</tbody>
          </table></div></div>
        </section>
      </div>
    </div>
  </AppShell>;
}

function EvalMetric({ label, value }: { label: string; value: number }) {
  return <div className="metric blue"><span>{label}</span><div><b>{(value * 100).toFixed(1)}%</b><em>ground truth</em></div></div>;
}
