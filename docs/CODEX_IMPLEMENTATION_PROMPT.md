# Codex Implementation Prompt

You are modifying an **existing repository**, not creating a replacement project.

Your task is to inspect the complete current codebase first, understand its architecture and existing functionality, and then incrementally upgrade it according to the requirements below.

Do not destroy or unnecessarily rewrite working features.

## Primary Objective

Upgrade the existing 5G RCA Copilot from a primarily log-oriented RAG prototype into a **multi-source KPI-guided Root Cause Analysis platform**.

The system must implement the following conceptual model:

```text
KPI / statistics
→ WHERE and WHEN something is wrong

Operational logs
→ WHY the issue may have occurred

Knowledge base
→ HOW the issue should be investigated or resolved

AI Assistant
→ connects these sources and explains the root cause
```

---

# Mandatory Language Rule

This is non-negotiable.

All user questions sent to the AI Assistant must be in **English**.

All AI-generated answers must be in **English**.

All suggested AI questions shown in the UI must be written in English.

Add model/system instructions that explicitly require English output.

Do not automatically translate AI output to Indonesian.

---

# Step 1 — Audit the Existing Repository

Before changing code:

1. Inspect the complete repository.
2. Identify:
   - frontend framework;
   - backend routes;
   - authentication;
   - database models;
   - migrations;
   - current log storage;
   - OpenSearch integration;
   - current retrieval implementation;
   - current semantic similarity implementation;
   - current Ollama integration;
   - current incident model;
   - Evaluation Lab;
   - Live Operations;
   - AI Assistant;
   - SSE/live log functionality.
3. Produce a concise internal implementation plan.
4. Reuse working components.
5. Do not duplicate existing services.

Do not start by generating a new project skeleton.

---

# Step 2 — Preserve Existing Functionality

The following existing product capabilities must continue working:

- authentication;
- protected routes;
- Live Operations;
- log viewer;
- log filters;
- incident management;
- AI Assistant sidebar;
- dataset management;
- Evaluation Lab;
- analysis history;
- Ollama support;
- current Docker/local development setup.

If a database migration is necessary, create a proper migration.

Do not delete existing user data structures without migration.

---

# Step 3 — Add KPI Context

Extend the incident domain model to support KPI context.

Add storage for:

```text
kpi_name
kpi_level
current_value
baseline_value
anomaly_score
forecast_value
threshold
```

Create appropriate relational tables rather than storing everything in arbitrary strings.

Use JSONB only when structure is genuinely flexible.

---

# Step 4 — Add Domain Mapping Configuration

Create configurable domain files:

```text
config/domain/kpi_mapping.json
config/domain/interface_mapping.json
```

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

Interface mapping example:

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

Create a reusable domain mapping service.

Do not use LLM inference to determine deterministic KPI/interface relationships.

---

# Step 5 — Implement AnomalyEvent Integration

Create:

```text
POST /api/integrations/anomaly-event
```

The endpoint must:

- authenticate service requests;
- validate the payload;
- reject malformed payloads;
- be idempotent based on external `event_id`;
- persist the original event payload;
- create or update an Incident;
- enrich the incident with KPI hierarchy;
- enrich related interfaces;
- enrich related components;
- set incident source to `ANOMALY`.

Create automated tests.

---

# Step 6 — Implement ForecastEvent Integration

Create:

```text
POST /api/integrations/forecast-event
```

The endpoint must:

- authenticate service requests;
- validate payload;
- enforce idempotency;
- store raw event payload;
- create/update Incident;
- enrich KPI hierarchy;
- enrich interfaces/components;
- set source to `FORECAST`.

Add automated tests.

---

# Step 7 — Implement Event Correlation

Add a deterministic IncidentCorrelationService.

For MVP correlate anomaly and forecast events using:

- same KPI or mapped KPI;
- same node or related component;
- configurable time window.

Default:

```text
10 minutes
```

When correlated:

```text
source = ANOMALY_FORECAST
```

Do not add a new ML model for correlation.

---

# Step 8 — Add Metrics Provider Abstraction

Create:

```text
MetricsProvider
```

Implement:

```text
CSVMetricProvider
VictoriaMetricsProvider
```

`CSVMetricProvider` must support local laptop development and historical replay.

`VictoriaMetricsProvider` must support future integration server usage.

Do not require VictoriaMetrics for basic local startup.

---

# Step 9 — Replace Prototype Retrieval

Inspect the existing retrieval service.

If lexical scoring is currently calculated in Python against an in-memory candidate set, replace the **final production/research path** with real OpenSearch BM25.

If semantic similarity currently uses deterministic feature hashing or another placeholder, replace the final path with a real embedding model.

Default embedding:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Keep provider abstraction.

---

# Step 10 — Implement Real OpenSearch Vector Retrieval

Create a proper OpenSearch `knn_vector` index.

Requirements:

- actual Sentence Transformer embeddings;
- HNSW/kNN vector search;
- raw text preserved;
- metadata preserved;
- source `log_id` preserved.

Embedding dimension must come from the configured model.

Do not globally hardcode 384.

---

# Step 11 — Implement KPI-Guided Candidate Filtering

Before BM25/kNN retrieval, restrict the candidate search using IncidentContext.

Use where available:

1. timestamp;
2. affected node;
3. KPI;
4. related interfaces;
5. related network functions;
6. severity;
7. trace ID;
8. session ID;
9. error code.

Default time window:

```text
±5 minutes
```

The user must be able to configure the time range in the Retrieval Inspector.

---

# Step 12 — Hybrid Retrieval

Run BM25 and semantic retrieval independently.

Normalize both score sets.

Use:

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

Persist/display:

- BM25 score;
- semantic score;
- final score;
- rank.

Support:

```text
Top-K = 5, 10, 20
```

---

# Step 13 — Context Engineering

After Top-K selection:

1. deduplicate;
2. remove configurable noise patterns;
3. preserve metadata;
4. sort final incident evidence chronologically;
5. assign evidence identifiers.

Evidence ID prefixes:

```text
K = KPI
L = Log
T = Topology/domain mapping
R = Resolution knowledge
```

---

# Step 14 — Upgrade EvidenceBundle

EvidenceBundle must now support:

```json
{
  "incident_id": "...",
  "incident_context": {},
  "kpi_evidence": [],
  "topology_evidence": [],
  "log_evidence": [],
  "knowledge_evidence": [],
  "retrieval_config": {},
  "candidate_count": 0,
  "ordered_context": "",
  "retrieval_latency_ms": 0
}
```

Keep backward compatibility where practical.

---

# Step 15 — Add Knowledge Base

Create a separate OpenSearch knowledge index:

```text
5g-knowledge
```

Support sanitized documents such as:

- troubleshooting SOP;
- runbook;
- known issue catalogue;
- historical resolved incident;
- interface documentation.

Create:

```text
KnowledgeRepository
KnowledgeRetrievalService
```

Knowledge retrieval must be separate from operational log retrieval.

Do not merge all documents into the operational log index.

---

# Step 16 — Knowledge-Based Resolution Suggestions

After root-cause evidence is assembled, retrieve knowledge relevant to:

- affected interface;
- affected network function;
- detected error;
- root-cause category.

Return knowledge evidence as:

```text
R1
R2
R3
```

The AI may use knowledge evidence when recommending investigation/resolution.

It must cite the corresponding R IDs.

---

# Step 17 — RCA Provider Architecture

Ensure the application uses a provider abstraction such as:

```text
RCAProvider
├── OllamaProvider
├── AurelProvider
└── MockProvider
```

Ollama remains the default standalone provider.

AurelProvider should be configurable by environment variable and ready for team integration.

Do not require paid OpenAI API access.

---

# Step 18 — Grounded RCA Prompt

Update the system prompt.

Mandatory rules:

```text
You are a 5G Core Network Root Cause Analysis assistant.

Always answer in English.

Use only the supplied operational evidence and knowledge evidence.

Do not invent network events, logs, KPI values, interfaces, or evidence IDs.

Clearly distinguish observation from inference.

Every important root-cause statement must cite one or more evidence IDs.

If operational evidence is insufficient, explicitly return INSUFFICIENT_EVIDENCE.

Use resolution knowledge only for recommended investigation or suggested resolution.

Never claim that a recommended action has already been executed.
```

---

# Step 19 — RCA Structured Output

Use a validated schema:

```json
{
  "status": "SUPPORTED | PARTIAL | INSUFFICIENT_EVIDENCE",

  "incident_summary": "...",

  "likely_root_cause": "...",

  "affected_components": [],

  "affected_interfaces": [],

  "reasoning_summary": "...",

  "evidence_ids": [],

  "recommended_investigation": [],

  "suggested_resolution": [
    {
      "action": "...",
      "knowledge_sources": []
    }
  ],

  "evidence_strength": "HIGH | MEDIUM | LOW"
}
```

Validate all evidence IDs after generation.

Reject hallucinated IDs.

Retry once if structured output is invalid.

---

# Step 20 — English-Only Chat Experience

Update frontend AI Assistant.

Requirements:

- input placeholder in English;
- suggested prompts in English;
- responses in English;
- system errors related to AI interaction in English.

Suggested prompts:

```text
What happened during this period?

What is the most likely root cause?

Which interface is affected?

Which logs provide the strongest evidence?

What should the NOC engineer investigate next?

What resolution does the knowledge base recommend?
```

---

# Step 21 — Upgrade Live Operations UI

Do not clone OpenSearch Dashboard completely.

Extend the existing page with:

- KPI summary;
- current anomaly state;
- forecast state;
- KPI timeline;
- related interfaces;
- related logs;
- AI Assistant sidebar.

The AI context must automatically include current screen filters.

---

# Step 22 — Retrieval Inspector

Add or enhance the Retrieval Inspector.

Display:

```text
Primary KPI
KPI Level
Related Interfaces
Related Components
Time Window
Candidate Count
Alpha
Top-K
Embedding Model
BM25 Score
Semantic Score
Final Score
Retrieval Latency
```

---

# Step 23 — Evidence Interaction

AI evidence citations must be clickable.

Example:

```text
[K1]
[L2]
[T1]
[R1]
```

Behavior:

- KPI evidence → highlight KPI information;
- log evidence → open raw log;
- topology evidence → display mapping;
- knowledge evidence → open knowledge source.

---

# Step 24 — Historical Replay Mode

Implement a lightweight replay mode.

It should allow historical KPI data to be replayed with a simulated clock.

Requirements:

```text
CSV historical KPI
→ replay
→ anomaly/forecast event or manually injected event
→ IncidentContext
→ historical OpenSearch logs
→ RAG
→ RCA
```

Do not require services to operate 24/7.

---

# Step 25 — Database Migration

Add normalized tables/models for:

```text
incident_kpi_context
incident_interfaces
incident_components
external_events
knowledge_documents
```

Use proper foreign keys and indexes.

Add Alembic migrations.

Do not delete or reset the existing database as an implementation shortcut.

---

# Step 26 — Anonymization and Sensitive Data

Never commit real customer/operator data.

Implement or document a sanitization layer.

Demo/sample datasets must use dummy:

- operator;
- node names;
- KPI/counter names when required;
- IP addresses;
- sensitive log fields.

Secrets must remain in environment variables.

---

# Step 27 — Evaluation Upgrade

For Lukas' retrieval research, support comparison:

```text
BM25
Semantic
Hybrid
KPI-Guided Hybrid
```

Metrics:

```text
Precision@K
Recall@K
HitRate@K
MRR
Context Precision
Context Recall
Retrieval Latency
```

Store experiment configuration and result.

---

# Step 28 — Keep Evaluation Offline

Do not make RAGAS or ground-truth evaluation a runtime blocking gate.

Runtime:

```text
Incident → RAG → RCA → UI
```

Evaluation:

```text
Historical Incident → RAG → RCA → Ground Truth → Metrics
```

---

# Step 29 — Local Development Constraints

The project must remain usable on a Windows laptop with limited resources.

Do not require:

- Kubernetes;
- multi-node OpenSearch;
- large LLM;
- VictoriaMetrics;
- all four student services;

for local development.

Local mode must support:

```text
single-node OpenSearch
PostgreSQL
FastAPI
Next.js
CSV KPI
Ollama
```

---

# Step 30 — Integration Environment

Prepare documentation/configuration for future K3s deployment, but do not make K3s mandatory for normal development.

Do not implement production-scale HA as part of this task.

---

# Step 31 — Automated Tests

Add tests for:

- KPI mapping;
- interface mapping;
- AnomalyEvent validation;
- ForecastEvent validation;
- event idempotency;
- event correlation;
- incident enrichment;
- OpenSearch BM25;
- embedding generation;
- OpenSearch kNN;
- hybrid score fusion;
- EvidenceBundle;
- knowledge retrieval;
- evidence ID validation;
- English response requirement;
- insufficient-evidence behavior;
- database migration.

Add at least one integration test covering:

```text
Event
→ Incident
→ KPI enrichment
→ Hybrid retrieval
→ EvidenceBundle
→ RCA provider
→ RCAResult
```

---

# Step 32 — Demo Data

Add sanitized/synthetic demo data sufficient to demonstrate:

1. normal KPI;
2. KPI degradation;
3. related interface mapping;
4. relevant logs;
5. irrelevant/noise logs;
6. knowledge-base resolution;
7. grounded RCA response.

---

# Step 33 — Mandatory End-to-End Demo

The final repository must allow the following demo:

```text
Login

→ select or replay a KPI incident

→ view KPI degradation

→ inspect mapped interfaces/components

→ ask in English:
  "What is the most likely root cause of this KPI degradation?"

→ system performs KPI-guided OpenSearch retrieval

→ EvidenceBundle is created

→ Ollama/Aurel provider generates RCA

→ user sees:
   KPI evidence
   log evidence
   affected interface
   root cause
   recommended investigation
   knowledge-based resolution

→ user asks:
  "Which evidence supports this conclusion?"

→ AI answers in English using existing evidence IDs.
```

---

# Step 34 — Documentation

Update:

```text
README.md
CODEBASE.md
architecture documentation
API documentation
environment variable documentation
database documentation
```

Document:

- current architecture;
- KPI + log dual-source model;
- evidence model;
- team integration contracts;
- local setup;
- Docker setup;
- optional K3s target;
- demo procedure;
- test procedure.

---

# Step 35 — Implementation Quality Rules

Do not:

- rewrite the project from scratch;
- silently remove working features;
- fake OpenSearch retrieval in the final path;
- use placeholder embeddings in the final path;
- hardcode real customer data;
- hardcode credentials;
- let the LLM invent evidence;
- perform automatic remediation;
- add unrelated features.

Prefer:

- small composable services;
- typed schemas;
- provider interfaces;
- deterministic mappings;
- explicit error handling;
- reusable repositories;
- migrations;
- automated tests.

---

# Final Completion Procedure

After implementation:

1. build backend;
2. build frontend;
3. run migrations;
4. start required local services;
5. create OpenSearch indices;
6. index demo logs;
7. index demo knowledge documents;
8. run automated tests;
9. run the end-to-end demo;
10. fix failures;
11. update documentation.

Do not claim completion until the critical demo works successfully.

At the end, provide a concise report containing:

- files added;
- files modified;
- database migrations;
- API endpoints added;
- architecture changes;
- tests added;
- commands used to run the system;
- known limitations;
- recommended next integration step for Nanda, Habibi, Lukas, and Aurel.