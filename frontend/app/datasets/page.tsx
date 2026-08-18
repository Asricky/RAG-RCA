"use client";

import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { ArrowPathIcon, ArrowUpTrayIcon, CheckCircleIcon, CircleStackIcon, TrashIcon } from "@heroicons/react/24/outline";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

type Dataset = {
  id: string;
  name: string;
  description?: string;
  source_type: string;
  status: "UPLOADED" | "INDEXING" | "INDEXED" | "FAILED";
  total_records: number;
  valid_records: number;
  rejected_records: number;
  indexed_records: number;
  index_progress: number;
  index_error?: string;
};

export default function Datasets() {
  const [items, setItems] = useState<Dataset[]>([]);
  const [busy, setBusy] = useState<string>("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (quiet = false) => {
    try {
      setItems(await api<Dataset[]>("/datasets"));
      if (!quiet) setError("");
    } catch (caught) {
      if (!quiet) setError(caught instanceof Error ? caught.message : "Datasets could not be loaded");
    }
  }, []);

  useEffect(() => {
    void load();
    const poll = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(poll);
  }, [load]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (!selected) return;
    setBusy("upload"); setError(""); setMessage("");
    const form = new FormData(); form.append("file", selected);
    try {
      const item = await api<Dataset>("/datasets/upload", { method: "POST", body: form });
      setMessage(`${item.valid_records.toLocaleString("en-US")} valid records · ${item.rejected_records.toLocaleString("en-US")} rejected`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setBusy(""); event.target.value = "";
    }
  }

  async function startIndex(id: string) {
    setBusy(id); setError(""); setMessage("");
    try {
      await api(`/datasets/${id}/index`, { method: "POST" });
      setMessage("The dataset was queued for indexing. Progress updates automatically.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Indexing failed");
    } finally { setBusy(""); }
  }

  async function remove(item: Dataset) {
    if (!confirm(`Delete dataset ${item.name}? Its indexed documents will also be deleted.`)) return;
    setBusy(item.id); setError("");
    try {
      await api(`/datasets/${item.id}`, { method: "DELETE" });
      setMessage("The dataset and its indexed documents were deleted.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Delete failed");
    } finally { setBusy(""); }
  }

  return <AppShell title="Datasets" subtitle="Upload, validate, and index log collections" actions={
    <button className="icon-btn" aria-label="Refresh datasets" onClick={() => void load()}><ArrowPathIcon /></button>
  }>
    <div className="page-content">
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => void load()}>Retry</button></div>}
      {message && <div className="success-banner"><span>{message}</span><button onClick={() => setMessage("")}>Dismiss</button></div>}
      <label className="upload-zone">
        <input type="file" accept=".csv,.json,.jsonl" disabled={Boolean(busy)} onChange={upload} />
        <ArrowUpTrayIcon />
        <h3>{busy === "upload" ? "Validating dataset..." : "Drop a dataset or click to upload"}</h3>
        <p>CSV, JSON, or JSONL · Up to 250 MB / 1,000,000 records · JSONL is recommended for large datasets</p>
      </label>
      <div className="panel">
        <div className="panel-title"><CircleStackIcon /><div><h3>Available datasets</h3><p>Synthetic and uploaded network logs</p></div></div>
        <div className="dataset-grid">{items.map((item) => <article key={item.id}>
          <div className="dataset-icon"><CircleStackIcon /></div>
          <div>
            <h4>{item.name}</h4><p>{item.description?.startsWith("[") ? "Legacy uploaded 5G log collection" : item.description}</p>
            <div className="dataset-meta"><span>{item.source_type}</span><span>{item.total_records.toLocaleString("en-US")} records</span><span className={item.status.toLowerCase()}>{item.status}</span></div>
            {item.status === "INDEXING" && <div className="index-progress"><i style={{ width: `${item.index_progress}%` }} /><span>{item.indexed_records.toLocaleString("en-US")} / {item.valid_records.toLocaleString("en-US")} · {item.index_progress}%</span></div>}
            {item.status === "FAILED" && item.index_error && <p className="index-error">{item.index_error}</p>}
          </div>
          <div className="dataset-actions">
            {item.status !== "INDEXED" && item.status !== "INDEXING" && <button className="primary-small" disabled={Boolean(busy)} onClick={() => void startIndex(item.id)}>{busy === item.id ? "Starting…" : "Index now"}</button>}
            {item.source_type === "UPLOAD" && <button className="icon-btn danger" aria-label={`Delete ${item.name}`} disabled={Boolean(busy) || item.status === "INDEXING"} onClick={() => void remove(item)}><TrashIcon /></button>}
            {item.status === "INDEXED" && <CheckCircleIcon className="dataset-ready" />}
          </div>
        </article>)}</div>
      </div>
    </div>
  </AppShell>;
}
