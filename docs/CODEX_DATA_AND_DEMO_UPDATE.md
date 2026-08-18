# Codex Task — Dataset Structure, English-Only Product, and Demo-Ready AI Assistant

You are modifying an existing repository.

Do NOT create a new project and do NOT rewrite the repository from scratch.

Before making any changes, read these files first:

- `AGENTS.md`
- `CODEBASE.md`
- `README.md`
- `docs/PRD_MULTI_SOURCE_RAG_RCA.md`
- `docs/CODEX_IMPLEMENTATION_PROMPT.md`
- `docs/DATABASE_AND_AI_SETUP.md` if it exists

The old/legacy PRD is historical documentation only and must not be used as the current product specification.

---

# 1. Primary Goal

Update the existing 5G RCA Copilot so that:

1. the new KPI research dataset has a clean and safe repository structure;
2. the project supports historical KPI data for development and replay;
3. all product-facing language is English;
4. all AI Assistant queries and responses are English;
5. the AI Assistant is fully usable for an end-to-end local demo;
6. existing working functionality is preserved;
7. private/raw research data is never committed to Git;
8. the project remains runnable on a Windows development laptop.

The final product principle is:

```text
KPI / statistics
→ WHERE and WHEN something is wrong

Operational logs
→ WHY something is wrong

Knowledge base
→ HOW the issue should be investigated or resolved

AI Assistant
→ connects the evidence and explains the RCA