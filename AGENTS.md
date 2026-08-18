# RAG-RCA Repository Instructions

## Source of Truth

The current product requirements are defined in:

- `docs/PRD_MULTI_SOURCE_RAG_RCA.md`

The implementation instructions are defined in:

- `docs/CODEX_IMPLEMENTATION_PROMPT.md`

The previous PRD is archived at:

- `docs/PRD_LEGACY.md`

`PRD_LEGACY.md` is historical documentation only.
Do NOT use it as the current implementation specification.

## Existing Codebase

Before making architectural changes, read:

- `CODEBASE.md`
- `README.md`
- `docs/DATABASE_AND_AI_SETUP.md`

Do not rewrite the project from scratch.

Preserve existing working functionality unless the current PRD explicitly
requires a change.

## Project Principle

KPI/statistics indicate WHERE and WHEN a problem occurs.

Operational logs provide evidence for WHY the problem occurs.

The knowledge base provides guidance for HOW the problem should be
investigated or resolved.

The AI Assistant connects these sources and produces grounded RCA.

## Team Boundaries

Nanda:
- KPI anomaly detection
- produces AnomalyEvent

Habibi:
- KPI forecasting
- produces ForecastEvent

Lukas:
- incident enrichment
- KPI-guided retrieval
- OpenSearch BM25
- semantic/vector retrieval
- hybrid score fusion
- context engineering
- EvidenceBundle

Aurel:
- grounded RCA generation
- consumes EvidenceBundle
- produces RCAResult

## AI Language

All user queries to the AI Assistant must be in English.

All AI-generated answers must be in English.

All suggested AI prompts in the UI must be in English.

## Development Rules

- Do not rewrite the repository from scratch.
- Use database migrations for schema changes.
- Preserve existing authentication and working UI features.
- Do not require Kubernetes for local development.
- Do not require paid OpenAI APIs.
- Ollama must remain supported.
- Never commit real operator/customer data.
- Never commit credentials or secrets.
- Never allow the LLM to invent evidence IDs.