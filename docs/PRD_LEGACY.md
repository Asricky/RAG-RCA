# Product Requirements Document
## 5G RCA Copilot — AI-Assisted Observability & Root Cause Analysis Platform

**Product Type:** Web-based observability and AI investigation platform  
**Primary User:** NOC Analyst / Network Engineer  
**Primary Research Focus:** Incident-Aware Hybrid Retrieval & Context Engineering untuk RCA log jaringan 5G  
**Frontend:** Next.js / React + TypeScript  
**Backend:** FastAPI / Python  
**Operational Log Store:** OpenSearch  
**Application Database:** PostgreSQL  
**LLM Runtime:** Ollama  
**Embedding:** Sentence Transformer yang configurable  
**Deployment MVP:** Docker Compose  
**Future Deployment:** K3s

---

# 1. Product Vision

5G RCA Copilot adalah platform observability berbasis web yang menggabungkan monitoring near-real-time log jaringan 5G dengan AI Assistant berbasis Retrieval-Augmented Generation (RAG). Sistem memungkinkan teknisi memonitor log AMF, SMF, UPF, melakukan filtering dan investigasi incident, lalu berinteraksi dengan AI Assistant yang secara otomatis mengambil evidence log relevan melalui hybrid retrieval BM25 dan semantic search.

Berbeda dengan chatbot generik, AI Assistant harus mengetahui konteks yang sedang dilihat pengguna seperti time range, node, severity, selected logs, dan incident yang sedang aktif. Setiap diagnosis harus dapat ditelusuri kembali ke raw log melalui evidence ID.

---

# 2. Product Goals

Sistem harus memungkinkan user untuk:

1. Login menggunakan email dan password.
2. Melihat log jaringan secara near-real-time.
3. Memfilter log berdasarkan waktu, node, severity, keyword, trace ID, session ID, atau error code.
4. Melihat grafik distribusi log dan error.
5. Memilih satu atau lebih log untuk dianalisis.
6. Membuat incident secara manual.
7. Membuka incident yang berasal dari modul lain.
8. Bertanya kepada AI Assistant dari panel kanan.
9. Membuat AI menganalisis konteks layar aktif.
10. Menjalankan hybrid retrieval terhadap OpenSearch.
11. Menampilkan Top-K evidence.
12. Menghasilkan RCA berbasis evidence.
13. Membuka evidence langsung dari jawaban AI.
14. Melakukan follow-up conversation.
15. Melihat detail retrieval BM25, semantic score, dan final score.
16. Menyimpan history percakapan dan analisis.
17. Mengupload dataset untuk kebutuhan demo dan eksperimen.
18. Menjalankan evaluation lab untuk menguji konfigurasi retrieval.
19. Menggunakan synthetic sample dataset tanpa data customer.

---

# 3. Scope Akademik Lukas

Kontribusi utama modul Lukas:

```text
IncidentContext
      +
OpenSearch Logs
      ↓
Candidate Filtering
      ↓
Lexical Retrieval BM25
      +
Semantic Retrieval
      ↓
Score Fusion
      ↓
Top-K Evidence
      ↓
Context Engineering
      ↓
EvidenceBundle
```

`EvidenceBundle` merupakan output utama penelitian Lukas.

Untuk prototype standalone:

```text
EvidenceBundle
      ↓
Internal RCA Adapter
      ↓
Ollama
      ↓
RCAResult
```

Pada integrasi kelompok, internal RCA adapter dapat diganti dengan:

```text
EvidenceBundle
      ↓
Aurel RCA API
```

tanpa mengubah retrieval pipeline.

---

# 4. System Architecture

```text
                         ┌─────────────────────┐
                         │      Browser        │
                         └──────────┬──────────┘
                                    │
                         HTTPS / REST / SSE
                                    │
                         ┌──────────▼──────────┐
                         │   Next.js Frontend  │
                         └──────────┬──────────┘
                                    │
                                  API
                                    │
                     ┌──────────────▼──────────────┐
                     │         FastAPI API          │
                     └──────────────┬──────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       │                            │                            │
       ▼                            ▼                            ▼
 Authentication                Observability                  AI/RAG
    Service                       Service                     Service
       │                            │                            │
       │                            │                 ┌──────────┴───────────┐
       │                            │                 │                      │
       ▼                            ▼                 ▼                      ▼
 PostgreSQL                  OpenSearch         Retrieval Engine        Ollama
                                                       │
                                            ┌──────────┴──────────┐
                                            ▼                     ▼
                                          BM25                Semantic
                                            │                     │
                                            └──────────┬──────────┘
                                                       ▼
                                                  Score Fusion
                                                       │
                                                       ▼
                                                  EvidenceBundle
```

---

# 5. Frontend Technology

Recommended stack:

```text
Next.js
React
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
TanStack Table
ECharts
SSE client
```

Frontend tidak boleh mengakses OpenSearch secara langsung.

Semua akses harus melalui FastAPI.

---

# 6. Backend Technology

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
OpenSearch Python Client
Sentence Transformers
HTTPX
JWT Authentication
Passlib / bcrypt
PostgreSQL
```

---

# 7. Main Navigation

Sidebar kiri:

```text
Live Operations
Incidents
Log Explorer
Datasets
Evaluation Lab
System
```

Untuk ADMIN:

```text
Users
Settings
```

Panel AI Assistant berada di sebelah kanan dan tersedia pada:

```text
Live Operations
Incidents
Log Explorer
```

---

# 8. Authentication

## 8.1 Login

Endpoint:

```text
POST /api/auth/login
```

Request:

```json
{
  "email": "analyst@example.com",
  "password": "password"
}
```

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": "...",
    "name": "Lukas",
    "role": "ANALYST"
  }
}
```

## 8.2 Roles

### ADMIN

Dapat:

- mengelola user;
- upload dataset;
- delete dataset;
- konfigurasi system;
- melihat seluruh audit;
- menjalankan evaluation;
- menggunakan AI Assistant.

### ANALYST

Dapat:

- monitoring log;
- membuat incident;
- melakukan AI analysis;
- melihat log;
- melihat analysis history.

---

# 9. Application Database — PostgreSQL

PostgreSQL digunakan untuk menyimpan data aplikasi.

OpenSearch hanya digunakan untuk log dan vector retrieval.

---

# 10. PostgreSQL Schema

## 10.1 `users`

```sql
users
-----
id                  UUID PRIMARY KEY
email               VARCHAR(255) UNIQUE NOT NULL
password_hash       TEXT NOT NULL
full_name           VARCHAR(255)
role                VARCHAR(50) NOT NULL
is_active           BOOLEAN DEFAULT TRUE
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ DEFAULT NOW()
last_login_at       TIMESTAMPTZ
```

Role:

```text
ADMIN
ANALYST
```

---

## 10.2 `refresh_tokens`

```sql
refresh_tokens
--------------
id                  UUID PRIMARY KEY
user_id             UUID REFERENCES users(id)
token_hash          TEXT NOT NULL
expires_at          TIMESTAMPTZ NOT NULL
revoked_at          TIMESTAMPTZ
created_at          TIMESTAMPTZ DEFAULT NOW()
```

---

## 10.3 `datasets`

```sql
datasets
--------
id                  UUID PRIMARY KEY
name                VARCHAR(255) NOT NULL
description         TEXT
source_type         VARCHAR(50)
original_filename   VARCHAR(255)
status              VARCHAR(50)
total_records       INTEGER DEFAULT 0
valid_records       INTEGER DEFAULT 0
rejected_records    INTEGER DEFAULT 0
indexed_records     INTEGER DEFAULT 0
uploaded_by         UUID REFERENCES users(id)
created_at          TIMESTAMPTZ DEFAULT NOW()
indexed_at          TIMESTAMPTZ
```

`source_type`:

```text
UPLOAD
SYNTHETIC
LIVE
```

`status`:

```text
UPLOADED
PROCESSING
INDEXED
FAILED
```

---

## 10.4 `incidents`

```sql
incidents
---------
id                  UUID PRIMARY KEY
incident_code       VARCHAR(100) UNIQUE NOT NULL
title               VARCHAR(255)
description         TEXT
incident_timestamp  TIMESTAMPTZ NOT NULL
severity            VARCHAR(50)
status              VARCHAR(50)
source_type         VARCHAR(50)
created_by          UUID REFERENCES users(id)
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ DEFAULT NOW()
resolved_at         TIMESTAMPTZ
```

Severity:

```text
INFO
WARNING
MAJOR
CRITICAL
```

Status:

```text
NEW
INVESTIGATING
ANALYZED
RESOLVED
```

Source type:

```text
MANUAL
ANOMALY
FORECAST
ANOMALY_FORECAST
```

---

## 10.5 `incident_nodes`

```sql
incident_nodes
--------------
id                  UUID PRIMARY KEY
incident_id         UUID REFERENCES incidents(id)
node_name           VARCHAR(255)
component_type      VARCHAR(50)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

Component:

```text
AMF
SMF
UPF
OTHER
```

---

## 10.6 `incident_metadata`

```sql
incident_metadata
-----------------
id                  UUID PRIMARY KEY
incident_id         UUID REFERENCES incidents(id)
metadata_key        VARCHAR(255)
metadata_value      TEXT
created_at          TIMESTAMPTZ DEFAULT NOW()
```

Contoh:

```text
trace_id
session_id
error_code
forecast_metric
anomaly_score
```

---

# 11. Conversation Database

## 11.1 `conversations`

```sql
conversations
-------------
id                  UUID PRIMARY KEY
incident_id         UUID REFERENCES incidents(id)
user_id             UUID REFERENCES users(id)
title               VARCHAR(255)
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ DEFAULT NOW()
```

Satu incident dapat mempunyai beberapa conversation.

---

## 11.2 `messages`

```sql
messages
--------
id                  UUID PRIMARY KEY
conversation_id     UUID REFERENCES conversations(id)
sender_type         VARCHAR(20)
content             TEXT NOT NULL
message_type        VARCHAR(50)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

Sender:

```text
USER
ASSISTANT
SYSTEM
```

Message type:

```text
TEXT
RCA
ERROR
STATUS
```

---

# 12. Analysis Database

## 12.1 `analyses`

```sql
analyses
--------
id                    UUID PRIMARY KEY
incident_id           UUID REFERENCES incidents(id)
conversation_id       UUID REFERENCES conversations(id)
user_message_id       UUID REFERENCES messages(id)
assistant_message_id  UUID REFERENCES messages(id)

question              TEXT
status                VARCHAR(50)

time_from             TIMESTAMPTZ
time_to               TIMESTAMPTZ

alpha                 NUMERIC(4,3)
top_k                 INTEGER
candidate_count       INTEGER

retrieval_latency_ms  INTEGER
llm_latency_ms        INTEGER
total_latency_ms      INTEGER

embedding_model       VARCHAR(255)
llm_provider          VARCHAR(100)
llm_model             VARCHAR(255)

created_at            TIMESTAMPTZ DEFAULT NOW()
```

Status:

```text
SUCCESS
PARTIAL
INSUFFICIENT_EVIDENCE
FAILED
```

---

## 12.2 `analysis_evidence`

```sql
analysis_evidence
-----------------
id                    UUID PRIMARY KEY
analysis_id           UUID REFERENCES analyses(id)
evidence_id           VARCHAR(20)
log_id                VARCHAR(255)
rank                  INTEGER
bm25_score            DOUBLE PRECISION
semantic_score        DOUBLE PRECISION
final_score           DOUBLE PRECISION
created_at            TIMESTAMPTZ DEFAULT NOW()
```

Raw log tidak perlu disalin ke PostgreSQL karena dapat dibaca kembali dari OpenSearch menggunakan `log_id`.

---

## 12.3 `analysis_results`

```sql
analysis_results
----------------
id                    UUID PRIMARY KEY
analysis_id           UUID REFERENCES analyses(id)
result_status         VARCHAR(50)
incident_summary      TEXT
likely_root_cause     TEXT
reasoning_summary     TEXT
evidence_strength     VARCHAR(20)
affected_components   JSONB
recommended_actions   JSONB
evidence_ids          JSONB
raw_llm_response      JSONB
created_at            TIMESTAMPTZ DEFAULT NOW()
```

---

# 13. UI Context Database

## `analysis_context`

Optional tetapi direkomendasikan:

```sql
analysis_context
----------------
id                    UUID PRIMARY KEY
analysis_id           UUID REFERENCES analyses(id)
selected_log_ids      JSONB
active_nodes          JSONB
severity_filter       JSONB
search_query          TEXT
trace_id              VARCHAR(255)
session_id            VARCHAR(255)
ui_context            JSONB
created_at            TIMESTAMPTZ DEFAULT NOW()
```

Ini memungkinkan penelitian terhadap bagaimana screen context memengaruhi retrieval.

---

# 14. Evaluation Database

## `evaluation_runs`

```sql
evaluation_runs
---------------
id                    UUID PRIMARY KEY
name                  VARCHAR(255)
dataset_id            UUID REFERENCES datasets(id)

alpha                 NUMERIC(4,3)
top_k                 INTEGER
time_before_minutes   INTEGER
time_after_minutes    INTEGER
embedding_model       VARCHAR(255)

status                VARCHAR(50)

started_at            TIMESTAMPTZ
completed_at          TIMESTAMPTZ
created_by            UUID REFERENCES users(id)
created_at            TIMESTAMPTZ DEFAULT NOW()
```

---

## `evaluation_results`

```sql
evaluation_results
------------------
id                    UUID PRIMARY KEY
evaluation_run_id     UUID REFERENCES evaluation_runs(id)

incident_id           UUID REFERENCES incidents(id)

precision_at_k        DOUBLE PRECISION
recall_at_k           DOUBLE PRECISION
hit_rate_at_k         DOUBLE PRECISION
mrr                    DOUBLE PRECISION

context_precision     DOUBLE PRECISION
context_recall        DOUBLE PRECISION

retrieval_latency_ms  INTEGER

created_at            TIMESTAMPTZ DEFAULT NOW()
```

---

# 15. Ground Truth Database

## `ground_truth`

```sql
ground_truth
------------
id                  UUID PRIMARY KEY
incident_id         UUID REFERENCES incidents(id)
root_cause          TEXT
notes               TEXT
validated_by        VARCHAR(255)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

---

## `ground_truth_evidence`

```sql
ground_truth_evidence
---------------------
id                  UUID PRIMARY KEY
ground_truth_id     UUID REFERENCES ground_truth(id)
log_id              VARCHAR(255)
relevance_level     INTEGER
created_at          TIMESTAMPTZ DEFAULT NOW()
```

Relevance:

```text
3 = critical evidence
2 = relevant
1 = supporting
```

---

# 16. Audit Database

## `audit_logs`

```sql
audit_logs
----------
id                  UUID PRIMARY KEY
user_id             UUID REFERENCES users(id)
action              VARCHAR(255)
resource_type       VARCHAR(100)
resource_id         UUID
details             JSONB
ip_address          VARCHAR(64)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

Contoh action:

```text
LOGIN
CREATE_INCIDENT
UPLOAD_DATASET
RUN_ANALYSIS
VIEW_LOG
DELETE_DATASET
RUN_EVALUATION
```

---

# 17. OpenSearch Data Model

Index default:

```text
5g-logs
```

OpenSearch document:

```json
{
  "log_id": "LOG-001",
  "@timestamp": "2026-08-12T10:03:21.012Z",
  "node": "SMF-01",
  "component": "SMF",
  "severity": "ERROR",
  "message": "PFCP request timed out waiting for UPF-01",
  "trace_id": "trace-123",
  "session_id": "session-001",
  "error_code": "PFCP_TIMEOUT",
  "container_name": "smf",
  "host": "node-01",
  "metadata": {},
  "search_text": "[SMF-01] [ERROR] [PFCP_TIMEOUT] PFCP request timed out waiting for UPF-01",
  "embedding": []
}
```

---

# 18. OpenSearch Mapping

Conceptual mapping:

```json
{
  "properties": {
    "log_id": {
      "type": "keyword"
    },
    "@timestamp": {
      "type": "date"
    },
    "node": {
      "type": "keyword"
    },
    "component": {
      "type": "keyword"
    },
    "severity": {
      "type": "keyword"
    },
    "message": {
      "type": "text"
    },
    "trace_id": {
      "type": "keyword"
    },
    "session_id": {
      "type": "keyword"
    },
    "error_code": {
      "type": "keyword"
    },
    "search_text": {
      "type": "text"
    },
    "metadata": {
      "type": "object"
    },
    "embedding": {
      "type": "knn_vector",
      "dimension": 384
    }
  }
}
```

Dimension harus mengikuti embedding model.

Tidak boleh diasumsikan selalu 384 jika model berubah.

---

# 19. Data Ingestion

Supported format:

```text
CSV
JSON
JSONL
```

User harus dapat:

```text
Datasets
→ Upload
→ Preview
→ Field Mapping
→ Validate
→ Index
```

Field mapping:

```text
source_time       → @timestamp
network_function  → component
instance           → node
log_level          → severity
body               → message
```

---

# 20. Synthetic Demo Dataset

Repository harus menyediakan synthetic logs minimal 300–500 record.

Minimal scenario:

### Scenario 1 — PFCP Failure

```text
UPF association degradation
↓
SMF PFCP timeout
↓
PDU session establishment failure
```

### Scenario 2 — AMF Registration Failure

```text
registration retry
↓
control-plane timeout
↓
UE registration failure
```

### Scenario 3 — UPF Degradation

```text
packet drop increase
↓
QoS degradation
↓
user-plane failure
```

Mayoritas dataset harus berupa normal/noise log sehingga retrieval benar-benar diuji.

---

# 21. Live Operations Page

Route:

```text
/operations
```

Layout:

```text
┌──────────── Sidebar ────────────┐
│                                 │
│    Main Observability Area      │ AI Assistant
│                                 │
└─────────────────────────────────┘
```

---

# 22. Top Filter Bar

Fields:

```text
Index / Dataset
Time Range
Node
Component
Severity
Keyword
Trace ID
Session ID
```

Controls:

```text
Refresh
Pause
Live
```

Live indicator:

```text
● LIVE
```

---

# 23. Live Log Summary Cards

Display:

```text
Logs/minute
Error Rate
Warning Rate
Active Incidents
Critical Incidents
```

---

# 24. Event Histogram

Chart menampilkan:

```text
log count over time
error count over time
severity distribution
```

User dapat select time window.

Selected window otomatis memperbarui:

```text
log table
AI UI context
retrieval context
```

---

# 25. Live Log Table

Columns:

```text
Timestamp
Node
Component
Severity
Message
Trace ID
Session ID
```

Requirements:

- virtualized;
- sortable;
- filterable;
- selectable;
- highlight severity;
- expandable row.

---

# 26. Live Log Streaming

Untuk MVP:

```text
Browser
   ↓
SSE
   ↓
FastAPI
   ↓
OpenSearch latest query
```

Backend melakukan incremental fetch berdasarkan latest timestamp.

Polling internal:

```text
1–2 detik configurable
```

Frontend menerima hanya data baru.

---

# 27. Log Selection

User dapat select beberapa log.

Toolbar muncul:

```text
3 logs selected

Analyze with AI
Find Related Logs
Create Incident
Clear Selection
```

---

# 28. Log Detail Drawer

Klik log menampilkan:

```text
Timestamp
Node
Component
Severity
Message
Raw JSON
Trace ID
Session ID
Error Code
```

Actions:

```text
Analyze with AI
Find Related Logs
Create Incident
```

---

# 29. AI Assistant Panel

Panel kanan selalu tersedia.

Header:

```text
AI RCA Assistant
```

Subheader menunjukkan context:

```text
Context:
SMF-01
10:03–10:05
3 selected logs
```

---

# 30. AI Chat Input

Placeholder:

```text
Ask about current logs...
```

Suggested prompts:

```text
Apa yang terjadi pada periode ini?
Apa kemungkinan root cause?
Log mana yang paling relevan?
Apakah ada hubungan antara SMF dan UPF?
Apa langkah investigasi berikutnya?
```

---

# 31. UI Context

Setiap chat request mengirim:

```json
{
  "question": "...",
  "conversation_id": "...",
  "incident_id": "...",
  "ui_context": {
    "time_from": "...",
    "time_to": "...",
    "selected_nodes": [],
    "severity": [],
    "selected_log_ids": [],
    "trace_id": null,
    "session_id": null,
    "keyword": null
  }
}
```

---

# 32. RAG Retrieval Flow

```text
Question
     +
UI Context
     +
IncidentContext
      ↓
Query Builder
      ↓
Time Filter
      ↓
Node Filter
      ↓
Metadata Filter
      ↓
Candidate Logs
      ↓
BM25 Search
      +
Semantic Search
      ↓
Normalization
      ↓
Score Fusion
      ↓
Top-K
      ↓
Context Engineering
      ↓
EvidenceBundle
```

---

# 33. Candidate Filtering

Default:

```text
±5 minutes
```

Configurable:

```text
1
5
10
15
30 minutes
```

Filter priority:

```text
timestamp
trace_id
session_id
node
severity
component
```

---

# 34. BM25 Retrieval

Default candidate:

```text
50
```

Return raw score.

---

# 35. Semantic Retrieval

Embedding query menggunakan embedding model yang sama dengan document.

Default candidate:

```text
50
```

Return similarity score.

---

# 36. Score Normalization

Default:

```text
Min-Max Normalization
```

Setiap score menjadi range:

```text
0–1
```

---

# 37. Hybrid Fusion

Formula:

```text
final_score =
alpha * normalized_BM25
+
(1-alpha) * normalized_semantic
```

Default:

```text
alpha = 0.5
```

Config:

```text
0.0 – 1.0
```

---

# 38. Top-K

Default:

```text
10
```

Option:

```text
5
10
20
```

---

# 39. Context Engineering

Pipeline:

```text
Top-K
↓
Chronological Ordering
↓
Deduplication
↓
Noise Removal
↓
Fact Extraction
↓
Evidence Labelling
↓
Context Formatter
```

---

# 40. EvidenceBundle

```json
{
  "incident_id": "INC-001",
  "retrieval_config": {
    "alpha": 0.5,
    "top_k": 10,
    "time_before_minutes": 5,
    "time_after_minutes": 5,
    "embedding_model": "..."
  },
  "candidate_count": 421,
  "evidence_logs": [
    {
      "evidence_id": "E1",
      "log_id": "...",
      "timestamp": "...",
      "node": "SMF-01",
      "severity": "ERROR",
      "message": "...",
      "bm25_score": 0.91,
      "semantic_score": 0.87,
      "final_score": 0.89
    }
  ],
  "ordered_context": "...",
  "retrieval_latency_ms": 328
}
```

---

# 41. LLM Generation

Default:

```text
Ollama
```

LLM adapter interface:

```text
LLMProvider
├── OllamaProvider
├── MockProvider
└── AurelProvider
```

---

# 42. AI System Prompt

```text
You are an AI assistant for 5G Core Network incident investigation.

Use only the supplied evidence.

Rules:
- Never invent log events.
- Every diagnosis must reference evidence IDs.
- Separate observation from inference.
- If evidence is insufficient, explicitly state it.
- Do not claim certainty unless the evidence supports it.
- Recommendations are investigation or remediation suggestions.
```

---

# 43. RCAResult

```json
{
  "status": "supported",
  "incident_summary": "...",
  "likely_root_cause": "...",
  "affected_components": [
    "SMF-01",
    "UPF-01"
  ],
  "reasoning_summary": "...",
  "evidence_ids": [
    "E1",
    "E2",
    "E4"
  ],
  "recommended_actions": [
    "...",
    "..."
  ],
  "evidence_strength": "medium"
}
```

Status:

```text
SUPPORTED
PARTIAL
INSUFFICIENT_EVIDENCE
```

---

# 44. Evidence Validation

Backend wajib memeriksa:

```text
RCAResult.evidence_ids
```

Semua evidence ID harus terdapat pada EvidenceBundle.

Jika LLM menghasilkan ID tidak valid:

```text
reject
retry once
```

Jika tetap invalid:

```text
return safe error / partial result
```

---

# 45. Chatbot Response UI

Response harus mempunyai komponen:

```text
Incident Summary
Likely Root Cause
Evidence Strength
Affected Components
Reasoning
Supporting Evidence
Recommended Actions
```

---

# 46. Clickable Evidence

Contoh:

```text
[E1] SMF-01 · ERROR · 10:03:21
PFCP request timed out
```

Klik evidence:

- membuka raw log;
- scroll ke log table;
- highlight row.

---

# 47. Retrieval Details

Setiap response memiliki:

```text
View Retrieval Details
```

Tampilkan:

```text
Candidate Count
Alpha
Top-K
Time Window
Embedding Model
Retrieval Latency
```

Table:

```text
Rank
Log ID
BM25
Semantic
Final
```

---

# 48. Chat Follow-Up

Follow-up default menggunakan:

```text
existing EvidenceBundle
conversation history
```

Retrieval tidak dijalankan ulang kecuali:

- user mengubah time window;
- meminta node lain;
- memilih Search More Evidence;
- pertanyaan membutuhkan evidence baru.

---

# 49. Search More Evidence

Button:

```text
Search More Evidence
```

Default action:

```text
time window ±5 → ±15
Top-K 10 → 20
```

Kemudian retrieval baru dijalankan.

---

# 50. Incidents Page

Route:

```text
/incidents
```

Columns:

```text
Incident ID
Timestamp
Title
Node
Severity
Source
Status
Last Analysis
```

---

# 51. Incident Detail Page

Header:

```text
INC-001
PDU Session Failure
CRITICAL
```

Summary:

```text
Timestamp
Nodes
Source
Description
Status
```

Tabs:

```text
Investigation
Logs
Evidence
History
```

AI panel tetap tersedia.

---

# 52. Log Explorer

Route:

```text
/logs
```

Filter:

```text
Time range
Node
Component
Severity
Keyword
Trace ID
Session ID
Error Code
```

Actions:

```text
Analyze
Create Incident
Add to AI Context
```

---

# 53. Datasets Page

Route:

```text
/datasets
```

Functions:

```text
Upload dataset
Preview
Field mapping
Validate
Index
Delete
```

Supported:

```text
CSV
JSON
JSONL
```

---

# 54. Evaluation Lab

Route:

```text
/evaluation
```

Parameters:

```text
Dataset
Alpha
Top-K
Time Window
Embedding Model
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

Optional future:

```text
Faithfulness
Answer Relevancy
RCA Accuracy
```

---

# 55. Evaluation Output

Table:

| Alpha | Top-K | Precision | Recall | Hit Rate | MRR | Latency |
|---|---:|---:|---:|---:|---:|---:|

Support chart:

```text
alpha vs recall
alpha vs precision
top-k vs latency
```

---

# 56. System Page

Route:

```text
/system
```

Display:

```text
Backend
PostgreSQL
OpenSearch
Embedding Model
Ollama
```

Status:

```text
Healthy
Degraded
Unavailable
```

---

# 57. Users Page

Admin only.

Functions:

```text
Create User
Disable User
Change Role
Reset Password
```

---

# 58. Main API Endpoints

Authentication:

```text
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
```

Users:

```text
GET    /api/users
POST   /api/users
PATCH  /api/users/{id}
DELETE /api/users/{id}
```

Logs:

```text
GET  /api/logs
GET  /api/logs/{log_id}
GET  /api/logs/stream
POST /api/logs/search-related
```

Datasets:

```text
GET  /api/datasets
POST /api/datasets/upload
POST /api/datasets/{id}/index
DELETE /api/datasets/{id}
```

Incidents:

```text
GET  /api/incidents
POST /api/incidents
GET  /api/incidents/{id}
PATCH /api/incidents/{id}
```

Chat:

```text
POST /api/conversations
GET  /api/conversations/{id}
POST /api/conversations/{id}/messages
```

Analysis:

```text
POST /api/analysis/retrieve
POST /api/analysis/run
GET  /api/analysis/{id}
POST /api/analysis/{id}/expand-evidence
```

Evaluation:

```text
POST /api/evaluation/run
GET  /api/evaluation/{id}
GET  /api/evaluation
```

Health:

```text
GET /api/health
GET /api/health/opensearch
GET /api/health/database
GET /api/health/ollama
```

---

# 59. API — Run AI Analysis

```text
POST /api/analysis/run
```

Request:

```json
{
  "conversation_id": "...",
  "incident_id": "...",
  "question": "Apa kemungkinan root cause?",
  "ui_context": {
    "time_from": "...",
    "time_to": "...",
    "selected_nodes": ["SMF-01"],
    "selected_log_ids": [],
    "severity": ["ERROR"]
  },
  "retrieval_config": {
    "alpha": 0.5,
    "top_k": 10
  }
}
```

Response:

```json
{
  "analysis_id": "...",
  "evidence_bundle": {},
  "rca_result": {},
  "timing": {
    "retrieval_ms": 331,
    "llm_ms": 4120,
    "total_ms": 4451
  }
}
```

---

# 60. SSE AI Progress

Endpoint:

```text
GET /api/analysis/{analysis_id}/events
```

Events:

```text
context_loaded
candidate_filtering
retrieval_started
retrieval_complete
evidence_selected
llm_started
llm_stream
analysis_complete
analysis_failed
```

Frontend menampilkan:

```text
✓ Context loaded
✓ 421 candidate logs found
✓ Top-10 evidence selected
● Generating RCA...
```

---

# 61. Security Requirements

- Password disimpan dengan hash.
- JWT memiliki expiration.
- Refresh token dapat direvoke.
- Secret hanya di `.env`.
- `.env` tidak boleh masuk Git.
- Customer logs tidak boleh masuk repository.
- Synthetic logs digunakan sebagai demo.
- Role-based route protection.
- API authentication wajib.
- Uploaded file dibatasi ukuran.
- Uploaded file harus divalidasi.
- Query ke OpenSearch tidak menerima DSL arbitrer dari frontend.
- Log aplikasi tidak mencetak password/token.

---

# 62. Configuration

`.env.example`:

```env
APP_ENV=development

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/rca_copilot

JWT_SECRET=
JWT_ACCESS_TOKEN_MINUTES=30
JWT_REFRESH_TOKEN_DAYS=7

OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_USER=
OPENSEARCH_PASSWORD=
OPENSEARCH_INDEX=5g-logs

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

DEFAULT_ALPHA=0.5
DEFAULT_TOP_K=10
DEFAULT_TIME_WINDOW_BEFORE=5
DEFAULT_TIME_WINDOW_AFTER=5

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=

LIVE_LOG_POLL_SECONDS=2
```

---

# 63. Repository Structure

```text
5g-rca-copilot/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   │   ├── auth/
│   │   ├── logs/
│   │   ├── incidents/
│   │   ├── assistant/
│   │   ├── datasets/
│   │   └── evaluation/
│   ├── lib/
│   ├── hooks/
│   └── types/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── logs/
│   │   │   ├── retrieval/
│   │   │   ├── context/
│   │   │   ├── llm/
│   │   │   ├── incidents/
│   │   │   └── evaluation/
│   │   ├── database/
│   │   └── core/
│   └── alembic/
│
├── data/
│   ├── sample_logs.jsonl
│   ├── sample_incidents.json
│   └── sample_ground_truth.json
│
├── scripts/
│
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

# 64. Docker Services

`docker-compose.yml`:

```text
frontend
backend
postgres
opensearch
```

Optional:

```text
ollama
```

Target ports:

```text
Frontend     : 3000
Backend      : 8000
PostgreSQL   : 5432
OpenSearch   : 9200
Ollama       : 11434
```

---

# 65. Demo Flow

Mandatory demo:

```text
Login
↓
Load synthetic dataset
↓
Open Live Operations
↓
Observe error spike
↓
Select suspicious logs
↓
Analyze with AI
↓
RAG retrieval
↓
AI RCA appears
↓
Open evidence E1
↓
Raw source log highlighted
↓
Open retrieval details
↓
Show BM25 + semantic + final score
↓
Ask follow-up
```

---

# 66. MVP Definition

MVP dianggap selesai jika:

- login berfungsi;
- PostgreSQL migration berjalan;
- OpenSearch tersedia;
- sample log dapat di-index;
- Live Operations dapat menampilkan log;
- live refresh berjalan;
- log filtering bekerja;
- log selection bekerja;
- AI sidebar tersedia;
- screen context dikirim ke backend;
- BM25 retrieval bekerja;
- semantic retrieval bekerja;
- score fusion bekerja;
- Top-K evidence bekerja;
- EvidenceBundle dihasilkan;
- Ollama menghasilkan RCA;
- AI output mengandung evidence ID;
- evidence dapat dibuka;
- conversation tersimpan;
- analysis history tersimpan;
- custom dataset dapat diupload;
- evaluation retrieval dapat dijalankan;
- project dapat dijalankan dengan Docker Compose.

---

# 67. Non-Goals MVP

Belum wajib:

```text
Kafka
full distributed tracing
complete APM implementation
advanced service map
Kubernetes autoscaling
automatic remediation
self-healing
OAuth/SSO
multi-tenant
fine-tuning
training custom LLM
mobile application
```

---

# 68. Future Team Integration

## Nanda

```text
AnomalyEvent
↓
POST /api/integrations/anomaly-event
↓
Incident
```

## Habibi

```text
ForecastEvent
↓
POST /api/integrations/forecast-event
↓
Incident
```

## Aurel

```text
EvidenceBundle
↓
POST Aurel API
↓
RCAResult
```

Provider:

```text
LLM_PROVIDER=aurel
```

---

# 69. Codex Implementation Constraints

Codex harus:

1. Membuat repository yang benar-benar runnable.
2. Tidak meninggalkan TODO pada critical path.
3. Membuat database migrations.
4. Membuat seed admin user.
5. Membuat synthetic logs.
6. Membuat synthetic incidents.
7. Membuat ground truth.
8. Menyediakan Docker Compose.
9. Membuat OpenSearch index otomatis.
10. Membuat embedding ingestion.
11. Membuat BM25 retrieval.
12. Membuat vector retrieval.
13. Membuat score fusion.
14. Membuat EvidenceBundle.
15. Membuat Ollama provider.
16. Membuat AI Assistant sidebar.
17. Membuat live log monitoring.
18. Membuat SSE.
19. Membuat clickable evidence.
20. Membuat retrieval inspector.
21. Membuat audit/history.
22. Membuat Evaluation Lab.
23. Membuat unit test.
24. Membuat integration test.
25. Menjalankan test sebelum completion.
26. Membuat README setup yang lengkap.

---

# 70. Recommended Build Phases

### Phase 1 — Infrastructure

```text
Next.js
FastAPI
PostgreSQL
OpenSearch
Docker Compose
```

### Phase 2 — Authentication

```text
users
roles
JWT
login UI
protected routes
```

### Phase 3 — Log Ingestion

```text
upload
validation
mapping
OpenSearch indexing
embedding
```

### Phase 4 — Observability UI

```text
Live Operations
histogram
log table
filters
SSE
```

### Phase 5 — Retrieval

```text
candidate filtering
BM25
semantic search
score fusion
Top-K
```

### Phase 6 — Context Engineering

```text
ordering
deduplication
noise reduction
EvidenceBundle
```

### Phase 7 — AI Assistant

```text
chat panel
Ollama
RCA structured output
evidence citation
```

### Phase 8 — Incident Management

```text
incident CRUD
conversation
history
```

### Phase 9 — Research Tools

```text
retrieval inspector
evaluation lab
ground truth
```

### Phase 10 — Testing & Demo

```text
seed dataset
demo incident
E2E test
README
```

---

# 71. Final Product Principle

Produk tidak boleh bekerja seperti:

```text
User
↓
LLM
↓
Answer
```

Produk harus selalu memperlihatkan pipeline:

```text
Current Monitoring Context
        ↓
Candidate Filtering
        ↓
Hybrid Retrieval
        ↓
Top-K Evidence
        ↓
EvidenceBundle
        ↓
LLM Reasoning
        ↓
RCA
        ↓
Traceable Source Logs
```

Setiap jawaban AI harus dapat dijawab dengan pertanyaan:

> “AI mengambil kesimpulan tersebut dari log yang mana?”

dan sistem harus mampu menunjukkan bukti tersebut secara langsung.