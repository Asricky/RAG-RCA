# Product Requirements Document
## 5G RCA Copilot — Multi-Source KPI, Log Evidence, and Knowledge-Grounded RCA

**Project:** RAG-RCA / 5G RCA Copilot  
**Product Type:** AI-assisted observability and Root Cause Analysis platform  
**Primary Frontend:** Next.js + React + TypeScript  
**Backend:** FastAPI + Python  
**Application Database:** PostgreSQL  
**Log Search Engine:** OpenSearch  
**Metric Source:** VictoriaMetrics  
**LLM Runtime:** Ollama / pluggable RCA provider  
**Embedding:** Configurable Sentence Transformer  
**Integration Target:** Docker locally, K3s/Kubernetes on integration server

---

# 1. Product Vision

5G RCA Copilot is an observability and AI investigation platform for 5G Core Network operations.

The platform combines three types of information:

```text
KPI / Statistics
→ WHERE and WHEN something is wrong

Operational Logs
→ WHY something may be wrong

Knowledge Base
→ HOW the issue should be investigated or resolved
```

The AI Assistant connects these information sources and produces:

- incident explanation;
- likely root cause;
- affected network functions/interfaces;
- supporting KPI evidence;
- supporting log evidence;
- recommended investigation steps;
- suggested resolution based on the knowledge base.

All RCA claims must be traceable to evidence.

---

# 2. Language Requirement

This requirement is mandatory.

## AI User Queries

All questions submitted to the AI Assistant must be written in **English**.

Example:

```text
Why did the PDU Session Establishment Success Ratio drop on PCC-01?
```

## AI Responses

All AI-generated responses must be in **English**.

The model must not answer in Indonesian even if the log messages contain mixed-language data.

## Suggested Questions

All suggested prompts displayed in the UI must also be in English.

Examples:

```text
What happened during this period?

What is the most likely root cause?

Which logs provide the strongest evidence?

Which interface appears to be affected?

What should the NOC engineer investigate next?

What resolution is recommended by the knowledge base?
```

---

# 3. System Principle

The final reasoning chain must follow:

```text
KPI degradation / anomaly / forecast
               ↓
        Incident Context
               ↓
KPI hierarchy and interface mapping
               ↓
Related Network Functions
               ↓
Operational Log Retrieval
               ↓
      EvidenceBundle
               ↓
        Grounded RCA
               ↓
Knowledge Base Retrieval
               ↓
Resolution Recommendation
               ↓
          RCAResult
```

---

# 4. Team Scope

## Nanda

Responsibility:

```text
VictoriaMetrics KPI
→ Random Cut Forest Anomaly Detection
→ AnomalyEvent
```

Nanda does not perform RCA.

---

## Habibi

Responsibility:

```text
VictoriaMetrics KPI
→ Random Cut Forest Forecasting
→ ForecastEvent
```

Habibi does not perform RCA.

---

## Lukas

Responsibility:

```text
IncidentContext
+
KPI context
+
OpenSearch logs
+
domain mappings
        ↓
KPI-guided hybrid retrieval
        ↓
EvidenceBundle
```

Lukas owns:

- incident enrichment;
- KPI/interface mapping;
- candidate filtering;
- BM25;
- semantic search;
- score fusion;
- Top-K retrieval;
- context engineering;
- evidence traceability.

---

## Aurel

Responsibility:

```text
EvidenceBundle
+
Knowledge Evidence
        ↓
Grounded LLM RCA
        ↓
RCAResult
```

Aurel does not implement retrieval from operational logs.

---

# 5. High-Level Architecture

```text
                         5G CORE NETWORK
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
             STATISTICS                     LOGS
                  │                           │
                  ▼                           ▼
          VictoriaMetrics                OpenSearch
                  │                           │
          ┌───────┴───────┐                   │
          ▼               ▼                   │
       Nanda            Habibi                 │
       RCF              RCF                    │
     Anomaly          Forecasting              │
       │                 │                     │
       ▼                 ▼                     │
 AnomalyEvent       ForecastEvent              │
       └────────┬────────┘                     │
                ▼                              │
       Incident Gateway                        │
                │                              │
       Incident Enrichment                     │
                │                              │
       KPI / Interface Map                     │
                │                              │
       Related Components                      │
                └──────────┬───────────────────┘
                           ▼
                     Lukas Retrieval
                           │
              BM25 + Semantic Retrieval
                           │
                      Score Fusion
                           │
                         Top-K
                           │
                  Context Engineering
                           │
                     EvidenceBundle
                           │
                           ▼
                         Aurel
                    Grounded RCA
                           │
               ┌───────────┴────────────┐
               │                        │
         Operational Evidence      Knowledge Base
               │                        │
               └───────────┬────────────┘
                           ▼
              Root Cause + Resolution
                           │
                           ▼
                    5G RCA Copilot
```

---

# 6. Data Sources

## 6.1 VictoriaMetrics

Used for:

- KPI time-series;
- statistics;
- current KPI values;
- historical KPI values;
- anomaly context;
- forecasting context.

The application must support an adapter interface.

```text
MetricsProvider
├── VictoriaMetricsProvider
└── CSVMetricProvider
```

`CSVMetricProvider` must remain available for laptop development and historical replay.

---

# 7. OpenSearch

Used as the primary operational evidence source.

OpenSearch stores:

- raw log text;
- timestamp;
- node;
- component;
- severity;
- trace/session metadata;
- error code;
- embedding vector.

The final retrieval implementation must use OpenSearch directly.

Do not use an in-memory fake BM25 implementation as the final research retrieval path.

---

# 8. Knowledge Base

Add a separate knowledge source for troubleshooting and resolution recommendations.

Supported document types:

- NOC SOP;
- troubleshooting runbook;
- historical resolved incident;
- known error catalogue;
- vendor troubleshooting guide;
- network-interface documentation;
- sanitized RCA reports.

Recommended OpenSearch index:

```text
5g-knowledge
```

Operational logs and knowledge documents must not use the same logical index.

Recommended separation:

```text
5g-operational-logs
5g-knowledge
```

---

# 9. KPI Domain Knowledge

KPI relationships must be represented as structured configuration.

Do not rely on LLM knowledge to determine the relationship.

Example:

```json
{
  "PDU_SESSION_ESTABLISHMENT_FAILURE_RATE": {
    "level": "L1",
    "related_interfaces": [
      "N1",
      "N11",
      "N4",
      "N10",
      "N7",
      "N40",
      "N28",
      "GY",
      "ESY"
    ]
  }
}
```

Another example:

```json
{
  "INITIAL_REGISTRATION_FAILURE_RATE": {
    "level": "L2",
    "related_interfaces": [
      "N1",
      "N8",
      "N35",
      "N12"
    ]
  }
}
```

---

# 10. Interface Mapping

Create a second structured mapping:

```json
{
  "N11": ["AMF", "SMF"],
  "N4": ["SMF", "UPF"],
  "N7": ["SMF", "PCF"],
  "N40": ["SMF", "CHF"],
  "N8": ["AMF", "UDM"],
  "N12": ["AMF", "AUSF"]
}
```

The configuration must be editable without changing Python source code.

Recommended location:

```text
config/domain/kpi_mapping.json
config/domain/interface_mapping.json
```

---

# 11. IncidentContext

Extend the current incident model.

Required structure:

```json
{
  "incident_id": "INC-001",

  "timestamp": "2026-08-12T12:00:00Z",

  "source": [
    "ANOMALY",
    "FORECAST"
  ],

  "affected_nodes": [
    "PCC-01"
  ],

  "severity": "CRITICAL",

  "kpi_context": {
    "primary_kpi": "PDU_SESSION_ESTABLISHMENT_FAILURE_RATE",
    "kpi_level": "L1",
    "current_value": 8.4,
    "baseline_value": 0.8,
    "anomaly_score": 0.92,
    "forecast_value": 9.1
  },

  "related_interfaces": [
    "N4",
    "N7",
    "N40"
  ],

  "related_components": [
    "SMF",
    "UPF",
    "PCF",
    "CHF"
  ]
}
```

Fields that are unavailable may be `null`.

---

# 12. AnomalyEvent Integration

Create:

```text
POST /api/integrations/anomaly-event
```

Expected payload:

```json
{
  "event_id": "ANOM-001",
  "timestamp": "2026-08-12T12:00:00Z",
  "node": "PCC-01",
  "kpi_name": "PDU_SESSION_ESTABLISHMENT_FAILURE_RATE",
  "current_value": 8.4,
  "anomaly_score": 0.92,
  "threshold": 0.75,
  "severity": "CRITICAL",
  "model_name": "RCF",
  "model_version": "1.0"
}
```

Requirements:

- validate payload;
- prevent duplicate event IDs;
- create/update Incident;
- store event metadata;
- use `source_type=ANOMALY`.

---

# 13. ForecastEvent Integration

Create:

```text
POST /api/integrations/forecast-event
```

Example:

```json
{
  "event_id": "FORECAST-001",
  "generated_at": "2026-08-12T11:55:00Z",
  "forecast_for": "2026-08-12T12:00:00Z",
  "node": "PCC-01",
  "kpi_name": "PDU_SESSION_ESTABLISHMENT_FAILURE_RATE",
  "current_value": 1.2,
  "predicted_value": 8.9,
  "threshold": 5.0,
  "risk_level": "HIGH",
  "model_name": "RCF",
  "model_version": "1.0"
}
```

---

# 14. Event Correlation

For MVP use deterministic rules.

Do not train another ML model.

Correlate AnomalyEvent and ForecastEvent when:

- node is identical or topology related;
- KPI is identical or hierarchically related;
- timestamps fall inside configurable correlation window.

Default:

```text
correlation_window = 10 minutes
```

If matched:

```text
source_type = ANOMALY_FORECAST
```

---

# 15. KPI Evidence

EvidenceBundle must contain KPI evidence independently of logs.

Example:

```json
{
  "evidence_id": "K1",
  "type": "KPI",
  "kpi_name": "PDU Session Establishment Failure Rate",
  "timestamp": "2026-08-12T12:00:00Z",
  "node": "PCC-01",
  "value": 8.4,
  "baseline": 0.8,
  "description": "A significant degradation was detected."
}
```

Prefix KPI evidence with:

```text
K1, K2, K3...
```

---

# 16. Log Evidence

Prefix operational log evidence with:

```text
L1, L2, L3...
```

Example:

```json
{
  "evidence_id": "L1",
  "type": "LOG",
  "log_id": "LOG-1922",
  "timestamp": "...",
  "component": "SMF",
  "severity": "ERROR",
  "message": "PFCP request timed out",
  "bm25_score": 0.89,
  "semantic_score": 0.84,
  "final_score": 0.865
}
```

---

# 17. Topology Evidence

Optional structured evidence can use:

```text
T1, T2...
```

Example:

```json
{
  "evidence_id": "T1",
  "type": "TOPOLOGY",
  "interface": "N4",
  "components": ["SMF", "UPF"]
}
```

---

# 18. Candidate Filtering

Before vector retrieval, narrow the search space.

Candidate filter should consider:

1. incident timestamp;
2. KPI;
3. affected node;
4. related interfaces;
5. related network functions;
6. severity;
7. trace ID;
8. session ID;
9. error code.

Default time range:

```text
incident_time ± 5 minutes
```

Allow:

```text
1
5
10
15
30 minutes
```

---

# 19. OpenSearch BM25

The final implementation must execute BM25 directly in OpenSearch.

Search fields should include:

```text
message
search_text
component
error_code
```

Boost exact technical identifiers.

---

# 20. Semantic Retrieval

Replace deterministic feature hashing with a real embedding model.

Default development model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Embedding provider:

```text
EmbeddingProvider
```

Must be configurable.

---

# 21. OpenSearch kNN / HNSW

Create an actual vector index.

The embedding dimension must be derived from the configured model.

Do not hardcode `384` globally.

Store:

- raw document;
- metadata;
- embedding.

---

# 22. Hybrid Retrieval

For research transparency run lexical and vector searches independently and fuse scores in the backend.

```text
normalized_bm25
normalized_semantic
```

Formula:

```text
final_score =
alpha * normalized_bm25
+
(1 - alpha) * normalized_semantic
```

Default:

```text
alpha = 0.5
```

Keep the individual scores.

---

# 23. Top-K

Default:

```text
10
```

Configurable options:

```text
5
10
20
```

---

# 24. Context Engineering

Pipeline:

```text
Retrieved logs
↓
deduplication
↓
noise filtering
↓
chronological ordering
↓
metadata preservation
↓
evidence labelling
↓
EvidenceBundle
```

Do not reorder evidence only according to retrieval rank when constructing the final incident timeline.

---

# 25. EvidenceBundle

Required final structure:

```json
{
  "incident_id": "INC-001",

  "incident_context": {},

  "kpi_evidence": [
    {}
  ],

  "topology_evidence": [
    {}
  ],

  "log_evidence": [
    {}
  ],

  "retrieval_config": {
    "alpha": 0.5,
    "top_k": 10,
    "time_window_minutes": 5,
    "embedding_model": "all-MiniLM-L6-v2"
  },

  "candidate_count": 324,

  "ordered_context": "...",

  "retrieval_latency_ms": 422
}
```

This remains the main output of Lukas' research module.

---

# 26. Knowledge Retrieval

Knowledge retrieval occurs separately from operational-log retrieval.

Query should be generated from:

- likely affected interface;
- error pattern;
- root-cause candidate;
- network function;
- incident category.

Return:

```text
R1
R2
R3
```

where `R` represents resolution knowledge.

---

# 27. RCA Input

Aurel/internal RCA provider receives:

```text
IncidentContext
+
KPI Evidence
+
Topology Evidence
+
Log Evidence
+
Knowledge Evidence
+
User Question
```

---

# 28. RCA Rules

The LLM must:

- use evidence only;
- distinguish observation and inference;
- cite evidence IDs;
- never invent evidence;
- explicitly communicate uncertainty;
- abstain if operational evidence is insufficient;
- use knowledge base for recommended resolution;
- never claim a resolution was executed automatically.

---

# 29. RCA Output

```json
{
  "status": "SUPPORTED",

  "incident_summary": "...",

  "likely_root_cause": "...",

  "affected_components": [
    "SMF",
    "UPF"
  ],

  "affected_interfaces": [
    "N4"
  ],

  "reasoning_summary": "...",

  "evidence_ids": [
    "K1",
    "L1",
    "L2",
    "T1"
  ],

  "recommended_investigation": [
    "..."
  ],

  "suggested_resolution": [
    {
      "action": "...",
      "knowledge_sources": ["R1"]
    }
  ],

  "evidence_strength": "MEDIUM"
}
```

---

# 30. Local LLM

Development default:

```text
Ollama
```

Provider design:

```text
RCAProvider
├── OllamaProvider
├── AurelProvider
└── MockProvider
```

No OpenAI API is required for normal operation.

---

# 31. AI Assistant Interface

The right-side AI Assistant panel remains a major UI feature.

It must understand the active screen context.

Context includes:

- current time range;
- selected KPI;
- selected node;
- selected interfaces;
- selected logs;
- active incident.

---

# 32. AI Assistant UI Language

The AI Assistant experience is **English only**.

Example question:

```text
Why did the PDU Session KPI degrade during this period?
```

Example response:

```text
The most likely cause is a communication issue on the N4 interface between the SMF and UPF.

Evidence:
[K1] The PDU Session Establishment KPI degraded significantly.
[L1] The SMF reported repeated PFCP request timeouts.
[L2] The UPF reported association loss.
[T1] The N4 interface connects the SMF and UPF.

Recommended investigation:
1. Verify PFCP connectivity.
2. Check UPF association status.
```

---

# 33. Live Operations Page

The dashboard should visually combine:

```text
KPI
+
Anomaly
+
Forecast
+
Related Logs
+
AI Assistant
```

Suggested layout:

```text
┌──────────────────────────────────────────────────────┐
│ KPI Cards / Anomaly / Forecast                       │
├──────────────────────────────────────────────────────┤
│ KPI Timeline                                          │
├───────────────────────────────┬──────────────────────┤
│ Related Logs                  │ AI RCA Assistant      │
│                               │                       │
│                               │                       │
└───────────────────────────────┴──────────────────────┘
```

---

# 34. KPI Page Components

Display:

- KPI name;
- KPI level;
- node;
- current value;
- anomaly score;
- forecast value;
- baseline;
- status;
- related interfaces.

---

# 35. Retrieval Inspector

Show:

- incident;
- selected KPI;
- related interfaces;
- related components;
- time window;
- candidate count;
- BM25 score;
- semantic score;
- fused score;
- alpha;
- Top-K;
- latency.

---

# 36. Knowledge Inspector

Add a section that shows which knowledge documents were used.

Display:

```text
[R1] N4 Interface Troubleshooting Guide
[R2] PFCP Association Recovery Runbook
```

---

# 37. Historical Replay

Add a development/testing mode.

Purpose:

Replay historical KPI and incident data as if it were live.

Flow:

```text
Historical KPI
↓
Replay clock
↓
Anomaly / forecast
↓
Incident
↓
Historical logs
↓
RAG
↓
RCA
```

This feature avoids requiring a 24/7 integration environment.

---

# 38. Database Changes

Preserve existing PostgreSQL tables.

Add or extend:

## `incident_kpi_context`

```text
id
incident_id
kpi_name
kpi_level
current_value
baseline_value
anomaly_score
forecast_value
threshold
created_at
```

## `incident_interfaces`

```text
id
incident_id
interface_name
created_at
```

## `incident_components`

```text
id
incident_id
component_name
created_at
```

## `external_events`

```text
id
external_event_id
event_type
source_service
payload JSONB
received_at
incident_id
```

Event type:

```text
ANOMALY
FORECAST
```

## `knowledge_documents`

```text
id
document_code
title
document_type
source
version
is_active
metadata JSONB
created_at
```

Actual searchable document chunks may remain in OpenSearch.

---

# 39. Data Anonymization

Mandatory.

Never commit:

- real operator name;
- sensitive KPI names if restricted;
- sensitive node identifiers;
- customer raw logs;
- credentials;
- real IPs if considered sensitive.

Support a sanitization layer.

Development/demo datasets must use anonymized or synthetic names.

---

# 40. Evaluation

## Lukas

Evaluate:

- Precision@K;
- Recall@K;
- HitRate@K;
- MRR;
- Context Precision;
- Context Recall;
- retrieval latency.

Compare:

```text
BM25
vs
Semantic
vs
Hybrid
vs
KPI-guided Hybrid
```

The `KPI-guided Hybrid` configuration is the proposed system.

---

# 41. Runtime vs Evaluation

RAGAS/evaluation must not block live output.

Runtime:

```text
Incident
→ RAG
→ RCA
→ UI
```

Evaluation:

```text
Historical Incident
→ RAG
→ RCA
→ Ground Truth
→ Metrics
```

---

# 42. Authentication

Preserve existing login and role-based authorization.

Roles:

```text
ADMIN
ANALYST
```

---

# 43. Development Environment

Laptop development must remain possible.

Local mode should support:

```text
CSV KPI
+
sample OpenSearch logs
+
single-node OpenSearch
+
PostgreSQL
+
Ollama
```

Do not require Kubernetes for local development.

---

# 44. Integration Environment

Kubernetes/K3s deployment is an integration target, not a requirement for every developer run.

Integration environment may contain:

- VictoriaMetrics;
- OpenSearch;
- PostgreSQL;
- frontend;
- backend;
- Nanda service;
- Habibi service;
- Lukas retrieval;
- Aurel RCA service;
- persistent storage.

---

# 45. 24/7 Requirement

The TA system is **not required to run 24/7**.

It must support:

- development runs;
- controlled integration testing;
- historical replay;
- scheduled near-real-time experiments.

Production-grade HA is out of scope.

---

# 46. Mandatory Acceptance Scenario

The system must support this demonstration:

```text
1. User logs in.

2. Historical or live KPI is displayed.

3. KPI degradation is detected or selected.

4. IncidentContext is created.

5. KPI-to-interface mapping identifies related interfaces.

6. Related network functions are identified.

7. OpenSearch logs are filtered around the incident.

8. BM25 and semantic retrieval are executed.

9. Top-K log evidence is selected.

10. EvidenceBundle contains KPI + topology + logs.

11. RCA provider produces a grounded root cause.

12. Knowledge retrieval provides resolution guidance.

13. UI displays:
    - root cause;
    - affected interface;
    - KPI evidence;
    - log evidence;
    - recommended investigation;
    - suggested resolution.

14. User asks a follow-up question in English.

15. AI answers in English and cites the existing evidence.
```

---

# 47. Non-Goals

Do not implement as part of this change:

- automatic remediation;
- self-healing;
- telco production HA;
- multi-node OpenSearch production cluster;
- new anomaly ML model inside Lukas' service;
- new forecasting ML model inside Lukas' service;
- fine-tuning an LLM;
- unrestricted agent execution;
- 24/7 production SLA.

---

# 48. Definition of Done

The improvement is complete when:

- KPI context exists in incidents;
- AnomalyEvent endpoint works;
- ForecastEvent endpoint works;
- correlation works;
- KPI/interface mapping works;
- interface/component enrichment works;
- OpenSearch BM25 is real;
- Sentence Transformer embedding is real;
- OpenSearch kNN works;
- hybrid fusion works;
- KPI-guided filtering works;
- EvidenceBundle contains KPI/log/topology evidence;
- knowledge index works;
- RCA can cite KPI, log, topology, and knowledge sources;
- AI query is English;
- AI answer is English;
- historical replay can produce at least one complete demonstration;
- existing UI/authentication functionality remains functional;
- automated tests pass;
- README and architecture documentation are updated.