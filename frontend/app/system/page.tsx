"use client";

import { useEffect, useState } from "react";
import { ArrowPathIcon, ServerStackIcon } from "@heroicons/react/24/outline";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

export default function System() {
  const [data, setData] = useState<any>();
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try { setData(await api("/health")); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The health check failed"); }
  }
  useEffect(() => { void load(); }, []);
  return <AppShell title="System" subtitle="Runtime health and model configuration" actions={<button className="secondary-btn" onClick={() => void load()}><ArrowPathIcon />Refresh health</button>}>
    <div className="page-content">
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => void load()}>Retry</button></div>}
      <div className="system-hero"><div><span className={data?.status === "Healthy" ? "live-badge" : "mode-badge"}><i />{data?.status || "Checking"}</span><h2>5G RCA Copilot runtime</h2><p>{data?.log_count || 0} logs available for retrieval</p></div><ServerStackIcon /></div>
      <div className="service-grid">{data && Object.entries(data.services).map(([name, status]) => <article key={name}><div className="service-icon"><ServerStackIcon /></div><div><span>{name.replace("_", " ")}</span><b>{String(status)}</b></div><i className={String(status).startsWith("Healthy") ? "ok" : "warn"} /></article>)}</div>
    </div>
  </AppShell>;
}
