# Database, Retrieval, KPI, and AI Setup

This guide covers the supported local configuration for 5G RCA Copilot. Keep secrets and private research data outside Git.

## Local configuration

`npm run dev` reads an optional `.env.local` file from the repository root:

```powershell
Copy-Item .env.local.example .env.local
npm run dev
```

The committed default uses SQLite, sanitized demo KPI data, OpenSearch on localhost, and Ollama. Restart the launcher after changing `.env.local`.

## Database

### SQLite for a laptop demo

```env
DATABASE_URL=sqlite:///./rca_copilot.db
```

The database is created under `backend/`. Use SQLite for local single-user development only.

### PostgreSQL through Docker

```powershell
docker compose up -d postgres opensearch
```

Use this connection when the backend itself runs on the host:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/rca_copilot
OPENSEARCH_URL=http://127.0.0.1:9200
```

For the full container stack, copy `.env.example` to `.env` and run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Replace `JWT_SECRET` before using any non-local environment.

### Migrations

The one-command launcher applies migrations automatically. To run them explicitly:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

## OpenSearch retrieval

The runtime retrieval path uses real OpenSearch BM25 and Sentence Transformer kNN. It does not silently switch to an in-memory semantic implementation.

```env
OPENSEARCH_URL=http://127.0.0.1:9200
OPENSEARCH_INDEX=5g-logs-st-v1
OPENSEARCH_KNOWLEDGE_INDEX=5g-knowledge-v1
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32
INDEX_BATCH_SIZE=256
KNOWLEDGE_TOP_K=3
```

Start OpenSearch and check it with:

```powershell
docker compose up -d opensearch
Invoke-RestMethod http://127.0.0.1:9200/_cluster/health
```

The first run may download the embedding model. Uploaded JSONL data is staged incrementally and OpenSearch bulk payloads are bounded by `INDEX_BATCH_SIZE`, so indexing does not require loading the complete upload into a single request.

Operational logs and knowledge documents use separate indices. Backend startup indexes the committed synthetic files into both indices. To regenerate and validate those files before startup:

```powershell
npm run data:generate
npm run data:validate
npm run dev
```

## KPI data

Safe default:

```env
KPI_SOURCE=demo
```

Historical local replay:

```env
KPI_SOURCE=raw
KPI_RAW_DIR=./data/kpi/raw
```

`data/kpi/raw/` is ignored by Git. The loader accepts the sanitized long-form demo schema and wide historical CSV files where the first date/time column is followed by one column per node. An empty or missing raw directory falls back to the demo file; an entirely empty data setup returns an empty catalog without failing application startup.

Never move raw KPI, log, or knowledge files into `data/demo/` unless they have been independently sanitized and approved for publication.

## Ollama: default local AI provider

Install Ollama, then prepare the default model:

```powershell
ollama pull llama3.2:3b
ollama serve
```

On Windows, Ollama may already run as a background service. Verify it with:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Local backend configuration:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT_SECONDS=120
LLM_ALLOW_MOCK_FALLBACK=true
```

For a backend container, use `http://host.docker.internal:11434` instead. The model receives English instructions and a bounded EvidenceBundle. Its structured output is validated, citations outside the bundle are discarded, and invalid output is retried before the safe fallback is used.

For a deterministic offline demonstration without invoking Ollama, set this locally and restart the app:

```env
LLM_PROVIDER=mock
```

MockProvider derives its summary, causal sequence, citations, and suggested resolution from the retrieved EvidenceBundle. It does not return a prewritten Scenario 01 answer.

## Optional OpenAI provider

OpenAI is not required for the demo. To enable it server-side:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=replace-locally
OPENAI_MODEL=gpt-5.6-sol
OPENAI_REASONING_EFFORT=medium
LLM_ALLOW_MOCK_FALLBACK=true
```

Keep the key only in `.env.local` or a deployment secret manager. Do not use a `NEXT_PUBLIC_` variable for secrets.

## Safety behavior

- AI questions and generated answers must be in English.
- Evidence IDs are validated against the supplied bundle.
- KPI evidence describes where and when a problem is visible.
- Operational logs are required before the assistant claims why it happened.
- When KPI evidence exists but log evidence is insufficient, the assistant returns `INSUFFICIENT_EVIDENCE`.
- Knowledge evidence may support investigation or resolution guidance, but cannot prove an operational root cause by itself.

## Health and troubleshooting

With the application running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/health/database
Invoke-RestMethod http://127.0.0.1:8000/api/health/opensearch
Invoke-RestMethod http://127.0.0.1:8000/api/health/embedding
Invoke-RestMethod http://127.0.0.1:8000/api/health/knowledge
```

If Analyze with AI returns `503`, start Docker Desktop and rerun `npm run dev`. If the provider shown in an analysis response is `mock-safe-fallback`, verify `ollama list`, the configured model name, and the Ollama base URL.
