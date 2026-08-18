"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowPathIcon, ChevronRightIcon, DocumentMagnifyingGlassIcon, MagnifyingGlassIcon, PauseIcon, PlayIcon, PlusIcon, SparklesIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import AppShell from "./AppShell";
import Assistant, { type KPIContext } from "./AssistantPanel";
import { api, fmt } from "@/lib/api";

export type NetworkLog = { log_id:string; "@timestamp":string; node:string; component:string; severity:string; message:string; trace_id:string; session_id:string; error_code:string; [key:string]:unknown };
type Filters = { node:string; component:string; severity:string; keyword:string; trace_id:string; session_id:string; error_code:string };
type Dataset = { id:string; name:string; source_type:string };
type MetricCatalog = { source:string; raw_available:boolean; items:KPIContext[] };
type MetricPoint = {
  timestamp:string; value:number; baseline_value?:number|null; forecast_value?:number|null;
  anomaly_score?:number|null; threshold?:number|null; status?:string;
};
type MetricSeries = { source:string; raw_available:boolean; context:KPIContext|null; points:MetricPoint[] };
const EMPTY_FILTERS:Filters = { node:"", component:"", severity:"", keyword:"", trace_id:"", session_id:"", error_code:"" };
const metricKey = (item: KPIContext) => `${item.kpi_name}::${item.node}`;
const REPLAY_WINDOW = 24;
const REPLAY_INTERVAL_MS = 1500;

export default function LogWorkspace({ explorer=false }:{ explorer?:boolean }) {
  const [logs,setLogs]=useState<NetworkLog[]>([]), [summary,setSummary]=useState<any>(null), [selected,setSelected]=useState<Set<string>>(new Set()), [detail,setDetail]=useState<NetworkLog|null>(null);
  const [paused,setPaused]=useState(false), [loading,setLoading]=useState(true), [error,setError]=useState(""), [filters,setFilters]=useState<Filters>(EMPTY_FILTERS), [refreshKey,setRefreshKey]=useState(0);
  const [assistantOpen,setAssistantOpen]=useState(false), [analyzeRequest,setAnalyzeRequest]=useState(0), [datasets,setDatasets]=useState<Dataset[]>([]), [datasetId,setDatasetId]=useState(""), [incidents,setIncidents]=useState<any[]>([]);
  const [actionMessage,setActionMessage]=useState(""), [actionBusy,setActionBusy]=useState(false);
  const [metricCatalog,setMetricCatalog]=useState<MetricCatalog>({source:"empty",raw_available:false,items:[]}), [selectedMetric,setSelectedMetric]=useState(""), [metricSeries,setMetricSeries]=useState<MetricSeries|null>(null);
  const [replayIndex,setReplayIndex]=useState(0);

  useEffect(()=>{
    Promise.all([api<Dataset[]>("/datasets"),api<any[]>("/incidents"),api<MetricCatalog>("/metrics/kpis")])
      .then(([ds,ins,metrics])=>{
        setDatasets(ds);setIncidents(ins);setMetricCatalog(metrics);
        if(ds[0])setDatasetId(ds[0].id);
        const preferred=metrics.items.find(item=>item.kpi_name.includes("PDU_SESSION"))||metrics.items[0];
        if(preferred)setSelectedMetric(metricKey(preferred));
      }).catch(caught=>setError(caught instanceof Error?caught.message:"The workspace could not be loaded"));
  },[]);

  useEffect(()=>{
    if(!selectedMetric){setMetricSeries(null);return}
    const [kpiName,node]=selectedMetric.split("::");
    const query=new URLSearchParams({kpi_name:kpiName,node,limit:"240"});
    void api<MetricSeries>(`/metrics/series?${query}`).then(setMetricSeries).catch(caught=>setError(caught instanceof Error?caught.message:"KPI history could not be loaded"));
  },[selectedMetric,refreshKey]);

  useEffect(()=>{
    if(explorer)return;
    setFilters(EMPTY_FILTERS);
  },[selectedMetric,explorer]);

  useEffect(()=>{
    const points=metricSeries?.points||[];
    if(!points.length){setReplayIndex(0);return}
    const focus=points.findIndex(point=>point.timestamp===metricSeries?.context?.timestamp);
    setReplayIndex(focus>=0?focus:Math.min(points.length-1,REPLAY_WINDOW-1));
  },[metricSeries]);

  useEffect(()=>{
    const points=metricSeries?.points||[];
    if(paused||explorer||points.length<2)return;
    const timer=window.setInterval(()=>setReplayIndex(current=>{
      if(current<points.length-1)return current+1;
      const focus=points.findIndex(point=>point.timestamp===metricSeries?.context?.timestamp);
      return Math.max(0,(focus>=0?focus:points.length-1)-Math.floor(REPLAY_WINDOW/2));
    }),REPLAY_INTERVAL_MS);
    return()=>window.clearInterval(timer);
  },[metricSeries,paused,explorer]);

  const activeDataset=useMemo(()=>datasets.find(item=>item.id===datasetId),[datasets,datasetId]);
  const datasetFilter=activeDataset?.source_type==="UPLOAD"?datasetId:"";
  useEffect(()=>{
    let active=true;
    const timer=window.setTimeout(async()=>{
      setLoading(true);setError("");
      try{
        const entries={...filters,...(datasetFilter?{dataset_id:datasetFilter}:{})};
        const query=new URLSearchParams(Object.entries(entries).filter(([,value])=>value));
        const data=await api<any>(`/logs?limit=200&${query}`);
        if(active){setLogs(data.items);setSummary(data.summary)}
      }catch(caught){if(active)setError(caught instanceof Error?caught.message:"Logs could not be loaded")}
      finally{if(active)setLoading(false)}
    },filters.keyword?350:0);
    return()=>{active=false;clearTimeout(timer)};
  },[filters,refreshKey,datasetFilter]);
  useEffect(()=>setSelected(new Set()),[filters,datasetId]);
  useEffect(()=>{
    if(paused||explorer||datasetFilter)return;
    let cancelled=false,source:EventSource|null=null,retry:number|undefined;
    const connect=async()=>{try{const{ticket}=await api<{ticket:string}>("/logs/stream-ticket",{method:"POST"});if(cancelled)return;source=new EventSource(`/api/logs/stream?ticket=${encodeURIComponent(ticket)}`);source.addEventListener("logs",event=>{const incoming=JSON.parse((event as MessageEvent).data) as NetworkLog[];setLogs(current=>[...incoming,...current.filter(row=>!incoming.some(next=>next.log_id===row.log_id))].slice(0,200))});source.onerror=()=>{source?.close();if(!cancelled)retry=window.setTimeout(connect,2000)}}catch(caught){if(!cancelled){setError(caught instanceof Error?caught.message:"The live stream was disconnected");retry=window.setTimeout(connect,3000)}}};
    void connect();return()=>{cancelled=true;source?.close();if(retry)clearTimeout(retry)};
  },[paused,explorer,datasetFilter]);

  const selectedLogs=useMemo(()=>logs.filter(row=>selected.has(row.log_id)),[logs,selected]);
  const toggle=(id:string)=>setSelected(current=>{const next=new Set(current);next.has(id)?next.delete(id):next.add(id);return next});
  function analyze(ids=[...selected]){if(!ids.length){setActionMessage("Select at least one log to analyze.");return}setSelected(new Set(ids));setAssistantOpen(true);setAnalyzeRequest(value=>value+1);setActionMessage(`${ids.length} log${ids.length===1?"":"s"} sent to the AI RCA Assistant.`)}
  async function findRelated(ids=[...selected]){if(!ids.length||actionBusy)return;setActionBusy(true);setError("");try{const bundle=await api<any>("/logs/search-related",{method:"POST",body:JSON.stringify({log_ids:ids,top_k:20,question:"Find causally related 5G network events"})});const related=(bundle.log_evidence||bundle.evidence_logs) as NetworkLog[];setLogs(related);setSelected(new Set(related.map(row=>row.log_id)));setActionMessage(`${related.length} related logs found among ${bundle.candidate_count} candidates.`);setDetail(null)}catch(caught){setError(caught instanceof Error?caught.message:"Related logs could not be found")}finally{setActionBusy(false)}}
  async function createIncident(ids=[...selected]){if(!ids.length||actionBusy)return;const context=logs.filter(row=>ids.includes(row.log_id));setActionBusy(true);setError("");try{const item=await api<any>("/incidents",{method:"POST",body:JSON.stringify({title:`Investigation: ${[...new Set(context.map(row=>row.component))].join(" / ")} event`,description:`Created from ${ids.length} selected logs (${ids.join(", ")}).`,incident_timestamp:context[0]?.["@timestamp"]||new Date().toISOString(),severity:context.some(row=>row.severity==="CRITICAL")?"CRITICAL":"MAJOR",nodes:[...new Set(context.map(row=>row.node))],source_type:"MANUAL"})});setIncidents(current=>[item,...current]);window.dispatchEvent(new Event("rca:incidents-changed"));setActionMessage(`${item.incident_code} was created from ${ids.length} logs.`);setDetail(null)}catch(caught){setError(caught instanceof Error?caught.message:"The incident could not be created")}finally{setActionBusy(false)}}

  const replayPoint=metricSeries?.points[replayIndex];
  const activeKpi=useMemo<KPIContext|null|undefined>(()=>{
    const context=metricSeries?.context;
    if(!context||!replayPoint)return context;
    return {
      ...context,
      timestamp:replayPoint.timestamp,
      current_value:replayPoint.value,
      baseline_value:replayPoint.baseline_value,
      forecast_value:replayPoint.forecast_value,
      anomaly_score:replayPoint.anomaly_score,
      threshold:replayPoint.threshold,
      status:replayPoint.status||context.status,
    };
  },[metricSeries,replayPoint]);
  const kpiChart=(metricSeries?.points||[])
    .slice(Math.max(0,replayIndex-REPLAY_WINDOW+1),replayIndex+1)
    .map(point=>({...point,time:fmt(point.timestamp),baseline:point.baseline_value,forecast:point.forecast_value}));
  const actions=<><span className={explorer?"mode-badge":"live-badge"}><i/>{explorer?"SEARCH MODE":paused?"PAUSED":"LIVE"}</span>{!explorer&&<button className="secondary-btn" onClick={()=>setPaused(!paused)}>{paused?<PlayIcon/>:<PauseIcon/>}{paused?"Resume":"Pause"}</button>}<button className="icon-btn" aria-label="Refresh workspace" onClick={()=>setRefreshKey(value=>value+1)}><ArrowPathIcon/></button><button className="secondary-btn mobile-ai-toggle" onClick={()=>setAssistantOpen(true)}><SparklesIcon/>Ask AI</button></>;

  return <AppShell title={explorer?"Log Explorer":"Live Operations"} subtitle={explorer?"Search and correlate historical 5G Core events":"KPI-guided 5G Core observability and root cause analysis"} actions={actions}>
    <div className="operations-layout"><section className="operations-main">
      {error&&<div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setRefreshKey(value=>value+1)}>Retry</button></div>}{actionMessage&&<div className="success-banner" role="status"><span>{actionMessage}</span><button onClick={()=>setActionMessage("")}>Dismiss</button></div>}
      <div className={`filterbar ${explorer?"":"with-kpi"}`}><select aria-label="Dataset" value={datasetId} onChange={event=>setDatasetId(event.target.value)}>{datasets.length?datasets.map(item=><option value={item.id} key={item.id}>{item.name}</option>):<option value="">No datasets available</option>}</select>{!explorer&&<select aria-label="KPI" value={selectedMetric} onChange={event=>setSelectedMetric(event.target.value)}>{metricCatalog.items.length?metricCatalog.items.map(item=><option value={metricKey(item)} key={metricKey(item)}>{item.kpi_name.replaceAll("_"," ")} · {item.node}</option>):<option value="">No demo KPI data</option>}</select>}<FilterSelect label="Node" value={filters.node} values={["AMF-01","AMF-02","SMF-01","SMF-02","UPF-01","UPF-02"]} onChange={node=>setFilters({...filters,node})}/><FilterSelect label="Component" value={filters.component} values={["AMF","SMF","UPF"]} onChange={component=>setFilters({...filters,component})}/><FilterSelect label="Severity" value={filters.severity} values={["INFO","WARNING","ERROR","CRITICAL"]} onChange={severity=>setFilters({...filters,severity})}/><label className="search"><MagnifyingGlassIcon/><input aria-label="Search logs" placeholder="Search message or code…" value={filters.keyword} onChange={event=>setFilters({...filters,keyword:event.target.value})}/></label></div>
      {explorer&&<div className="explorer-filters"><input aria-label="Trace ID" placeholder="Trace ID" value={filters.trace_id} onChange={event=>setFilters({...filters,trace_id:event.target.value})}/><input aria-label="Session ID" placeholder="Session ID" value={filters.session_id} onChange={event=>setFilters({...filters,session_id:event.target.value})}/><input aria-label="Error code" placeholder="Error code" value={filters.error_code} onChange={event=>setFilters({...filters,error_code:event.target.value})}/><button className="secondary-btn" onClick={()=>setFilters(EMPTY_FILTERS)}>Clear filters</button></div>}
      {!explorer&&<><div className="metric-grid"><Metric label="Current KPI" value={activeKpi?`${activeKpi.current_value}%`:"—"} delta={activeKpi?.status||"no data"} tone="blue"/><Metric label="Anomaly score" value={activeKpi?.anomaly_score!=null?`${Math.round(activeKpi.anomaly_score*100)}%`:"—"} delta="selected event" tone="red"/><Metric label="Forecast value" value={activeKpi?.forecast_value!=null?`${activeKpi.forecast_value}%`:"—"} delta="projected" tone="amber"/><Metric label="Active incidents" value={incidents.filter(item=>item.status!=="RESOLVED").length} delta={`${incidents.filter(item=>item.severity==="CRITICAL"&&item.status!=="RESOLVED").length} critical`} tone="purple"/></div><div className="chart-card"><div className="card-head"><div><h3>{activeKpi?.kpi_name.replaceAll("_"," ")||"Historical KPI"}</h3><span>{activeKpi?`${activeKpi.kpi_level||"Unmapped"} · ${activeKpi.node} · ${metricSeries?.source}`:"Local demo remains available when private raw data is empty"}</span></div><div className="legend"><span><i className="cyan"/>Value</span><span><i className="red"/>Baseline</span></div></div><ResponsiveContainer width="100%" height={190}><AreaChart data={kpiChart}><CartesianGrid strokeDasharray="3 3" stroke="#233044"/><XAxis dataKey="time" stroke="#718096" tickLine={false}/><YAxis stroke="#718096" tickLine={false}/><Tooltip contentStyle={{background:"#101827",border:"1px solid #29364a",borderRadius:8}}/><Area type="monotone" dataKey="value" stroke="#18c7b5" fill="#18c7b522" strokeWidth={2}/><Area type="monotone" dataKey="baseline" stroke="#fb6470" fill="none" strokeWidth={1.5}/><Area type="monotone" dataKey="forecast" stroke="#f6b94a" fill="none" strokeDasharray="4 3"/></AreaChart></ResponsiveContainer><div className="kpi-context-row"><span>Interfaces <b>{activeKpi?.related_interfaces?.join(", ")||"Not mapped"}</b></span><span>Components <b>{activeKpi?.related_components?.join(", ")||"Not mapped"}</b></span><button className="secondary-btn" onClick={()=>setAssistantOpen(true)}><SparklesIcon/>Investigate KPI</button></div></div></>}
      {explorer&&<><div className="metric-grid"><Metric label="Logs / minute" value={summary?.logs_per_minute??"—"} delta="current view" tone="blue"/><Metric label="Error rate" value={`${summary?.error_rate??0}%`} delta="error + critical" tone="red"/><Metric label="Warning rate" value={`${summary?.warning_rate??0}%`} delta="current window" tone="amber"/><Metric label="Active incidents" value={incidents.filter(item=>item.status!=="RESOLVED").length} delta={`${incidents.filter(item=>item.severity==="CRITICAL"&&item.status!=="RESOLVED").length} critical`} tone="purple"/></div><div className="chart-card"><div className="card-head"><div><h3>Event volume</h3><span>Logs and errors over time</span></div><div className="legend"><span><i className="cyan"/>Logs</span><span><i className="red"/>Errors</span></div></div><ResponsiveContainer width="100%" height={190}><AreaChart data={summary?.timeline||[]}><CartesianGrid strokeDasharray="3 3" stroke="#233044"/><XAxis dataKey="time" stroke="#718096" tickLine={false}/><YAxis stroke="#718096" tickLine={false}/><Tooltip contentStyle={{background:"#101827",border:"1px solid #29364a",borderRadius:8}}/><Area type="monotone" dataKey="total" stroke="#18c7b5" fill="#18c7b522" strokeWidth={2}/><Area type="monotone" dataKey="errors" stroke="#fb6470" fill="none" strokeWidth={2}/></AreaChart></ResponsiveContainer></div></>}
      <div className="logs-card"><div className="card-head"><div><h3>{explorer?"Search results":"Related operational logs"}</h3><span>{logs.length} events in the current view</span></div>{selected.size>0&&<div className="selection-bar"><b>{selected.size} selected</b><button disabled={actionBusy} onClick={()=>analyze()}>Analyze with AI</button><button disabled={actionBusy} onClick={()=>void findRelated()}><DocumentMagnifyingGlassIcon/>Related</button><button disabled={actionBusy} onClick={()=>void createIncident()}><PlusIcon/>Incident</button><button onClick={()=>setSelected(new Set())}>Clear</button></div>}</div><div className="table-wrap"><table className="log-table"><thead><tr><th><input aria-label="Select all logs" type="checkbox" checked={logs.length>0&&selected.size===logs.length} onChange={event=>setSelected(event.target.checked?new Set(logs.map(row=>row.log_id)):new Set())}/></th><th>Timestamp</th><th>Node</th><th>Component</th><th>Severity</th><th>Message</th><th>Trace ID</th><th/></tr></thead><tbody>{loading?<tr><td colSpan={8} className="empty"><div className="spinner"/>Loading logs…</td></tr>:logs.length===0?<tr><td colSpan={8} className="empty">No logs match the active filters.</td></tr>:logs.map(log=><tr key={log.log_id} className={selected.has(log.log_id)?"selected":""}><td><input aria-label={`Select ${log.log_id}`} type="checkbox" checked={selected.has(log.log_id)} onChange={()=>toggle(log.log_id)}/></td><td className="mono">{fmt(log["@timestamp"])}</td><td><b>{log.node}</b></td><td><span className="component">{log.component}</span></td><td><span className={`severity ${log.severity.toLowerCase()}`}>{log.severity}</span></td><td className="message" onClick={()=>setDetail(log)}>{log.message}</td><td className="mono muted">{log.trace_id}</td><td><button aria-label={`Open ${log.log_id}`} className="row-open" onClick={()=>setDetail(log)}><ChevronRightIcon/></button></td></tr>)}</tbody></table></div></div>
    </section><Assistant open={assistantOpen} onClose={()=>setAssistantOpen(false)} selected={selectedLogs} filters={filters} kpiContext={activeKpi} analyzeRequest={analyzeRequest} onEvidence={log=>setDetail(log as NetworkLog)}/></div>
    {detail&&<div className="drawer-overlay" onClick={()=>setDetail(null)}><aside className="drawer" onClick={event=>event.stopPropagation()}><button aria-label="Close log detail" className="drawer-close" onClick={()=>setDetail(null)}><XMarkIcon/></button><span className={`severity ${detail.severity.toLowerCase()}`}>{detail.severity}</span><h2>{detail.node} · {detail.component}</h2><p className="drawer-message">{detail.message}</p><div className="drawer-actions"><button className="primary-small" onClick={()=>{analyze([detail.log_id]);setDetail(null)}}><SparklesIcon/>Analyze with AI</button><button className="secondary-btn" onClick={()=>void findRelated([detail.log_id])}><DocumentMagnifyingGlassIcon/>Related logs</button><button className="secondary-btn" onClick={()=>void createIncident([detail.log_id])}><PlusIcon/>Create incident</button></div><dl>{[["Timestamp",detail["@timestamp"]],["Log ID",detail.log_id],["Trace ID",detail.trace_id],["Session ID",detail.session_id],["Error code",detail.error_code||"—"]].map(([label,value])=><div key={String(label)}><dt>{String(label)}</dt><dd>{String(value)}</dd></div>)}</dl><h4>Raw JSON</h4><pre>{JSON.stringify(detail,null,2)}</pre></aside></div>}
  </AppShell>;
}

function FilterSelect({label,value,values,onChange}:{label:string;value:string;values:string[];onChange:(value:string)=>void}){return <select aria-label={label} value={value} onChange={event=>onChange(event.target.value)}><option value="">All {label.toLowerCase()}</option>{values.map(item=><option key={item}>{item}</option>)}</select>}
function Metric({label,value,delta,tone}:{label:string;value:string|number;delta:string;tone:string}){return <div className={`metric ${tone}`}><span>{label}</span><div><b>{value}</b><em>{delta}</em></div><i/></div>}
