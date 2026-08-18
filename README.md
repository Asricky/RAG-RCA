# 5G RCA Copilot

5G RCA Copilot is an evidence-grounded observability and root cause analysis prototype for 5G Core operations. It combines KPI context, topology mappings, OpenSearch BM25 + Sentence Transformer kNN retrieval, operational logs, and an English-only AI Assistant.

The repository ships only with sanitized synthetic demo data. Real KPI, log, and knowledge data must remain local and must never be committed.

## Run the local demo

Prerequisites:

- Node.js 20 or newer;
- [`uv`](https://docs.astral.sh/uv/) for the Python environment;
- Docker Desktop for OpenSearch retrieval;
- [Ollama](https://ollama.com/) for the default local AI provider.

Start Docker Desktop and wait until its engine is ready. Verify it from PowerShell:

```powershell
docker info
docker compose up -d opensearch
docker compose ps
```

Prepare the default Ollama model once:

```powershell
ollama pull llama3.2:3b
ollama list
```

If the Ollama Windows service is not already active, keep `ollama serve` running in a separate terminal.

From the repository root, run:

```powershell
npm run dev
```

The launcher installs missing dependencies, creates the safe demo dataset when needed, applies database migrations, starts OpenSearch through Docker, starts FastAPI on port `8000`, loads demo records into SQLite, indexes logs and knowledge in separate OpenSearch indices, and starts Next.js on port `3000`.

Open <http://localhost:3000> and sign in with:

```text
Email:    admin@5grca.local
Password: admin123
```

Stop all launcher-managed services with `Ctrl+C`.

If Ollama is unavailable, the default configuration uses a deterministic evidence-safe generation fallback so the UI can still be demonstrated. OpenSearch remains required because production retrieval deliberately has no in-memory semantic fallback.

## Demo workflow

1. Open **Live Operations**.
2. Select **PDU SESSION ESTABLISHMENT SUCCESS RATIO** on `SMF-01`.
3. Review the KPI chart, related interfaces, and correlated logs.
4. Click **Analyze with AI**.
5. Ask `Why did the PDU session establishment success ratio degrade on SMF-01?`.
6. Inspect KPI (`K*`), topology (`T*`), log (`L*`), and knowledge (`R*`) citations in the answer.
7. Confirm that the suggested resolution cites the synthetic PFCP runbook rather than uncited model knowledge.

The assistant must return `INSUFFICIENT_EVIDENCE` instead of claiming a root cause when KPI evidence exists but no supporting operational log evidence can be retrieved.

## Data safety and KPI modes

```text
data/demo/           committed sanitized demo data
data/kpi/raw/        local-only historical KPI files
data/logs/raw/       local-only operational logs
data/knowledge/raw/  local-only runbooks and references
```

All `raw/` and `processed/` research paths are ignored by Git. The default `KPI_SOURCE=demo` reads `data/demo/sample_kpi.csv`. To replay local historical KPI CSV files, copy them under `data/kpi/raw/` and set this in `.env.local`:

```env
KPI_SOURCE=raw
KPI_RAW_DIR=./data/kpi/raw
```

If the raw directory is empty, the application safely falls back to the sanitized demo KPI dataset. It never copies raw source files into a committed directory.

## Useful commands

```powershell
npm run dev           # full localhost demo
npm run dev:lan       # expose the frontend to devices on the same LAN
npm run setup         # install dependencies and prepare directories only
npm test              # backend tests followed by a frontend production build
npm run build         # frontend production build
npm run data:generate # regenerate all deterministic synthetic demo sources
npm run data:validate # validate cross-source KPI/log/knowledge alignment
npm run dev:backend   # backend only
```

API documentation is available at <http://localhost:8000/docs> while the backend is running.

To run every application service in containers instead, use:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The host-based `npm run dev` profile is recommended for normal development because Next.js and FastAPI reload automatically. Stop container services with `docker compose down`; named database and OpenSearch volumes are preserved.

For LAN mode, allow inbound TCP port `3000` in Windows Firewall. The API and OpenSearch remain bound to loopback; the Next.js server proxies browser API requests.

## Configuration

Copy the local example before changing defaults:

```powershell
Copy-Item .env.local.example .env.local
```

Ollama is the default no-paid-API provider. OpenAI is optional and server-side only. Never place provider keys in frontend environment variables or commit `.env.local`.

See [CODEBASE.md](CODEBASE.md) for the architecture and [docs/DATABASE_AND_AI_SETUP.md](docs/DATABASE_AND_AI_SETUP.md) for database, retrieval, KPI, and AI provider setup.

## Startup troubleshooting

- `docker info` fails: start Docker Desktop, then rerun `npm run dev`.
- OpenSearch is still starting: inspect `docker compose logs opensearch` and wait for `http://127.0.0.1:9200/_cluster/health`.
- The first analysis is slow: allow the Sentence Transformer model to finish loading and indexing 400 demo logs.
- Ollama is unavailable: run `ollama serve`, check `ollama list`, and verify the configured model name. The safe mock fallback remains available.
- Port `3000` or `8000` is occupied: stop the older launcher with `Ctrl+C` before starting a new one.
