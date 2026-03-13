# docs/AGENTS.md

## Overview

Repository knowledge base and external-facing specs. This directory documents implemented behavior; it is not a parking lot for stale proposals.

## Structure

```text
docs/
├── 01_prd.md                   # product scope and user-facing behavior
├── 02_architecture.md          # package boundaries, data flow, runtime model
├── 03_data_model.md            # backend entities and stored fields
├── 04_api_spec.md              # human-readable API guide
├── 05_ui_spec.md               # dashboard routes and behaviors
├── 06_security_privacy.md      # auth, SSRF, redaction, token handling
├── 07_operations.md            # env, deploy, runtime commands, health/ops
├── 08_bark_v2.md               # Bark-specific provider notes
├── 09_repo_structure.md        # repo layout and package boundaries
├── 10_edge.md                  # current edge-lite runtime behavior
├── 11_edge_lite_feasibility.md # tradeoffs and scope boundaries for lite mode
└── openapi.yaml                # API schema source of truth
```

## Where to Look

| Question | File |
|----------|------|
| What does the product do today? | `01_prd.md` |
| How do backend, frontend, worker, and edge fit together? | `02_architecture.md` |
| Which fields are stored for each model? | `03_data_model.md` |
| What are the endpoints and payloads? | `04_api_spec.md`, `openapi.yaml` |
| What does the dashboard actually expose? | `05_ui_spec.md` |
| How are auth, tokens, SSRF, and redaction handled? | `06_security_privacy.md` |
| How is the repo run or deployed? | `07_operations.md` |
| What does Bark integration support? | `08_bark_v2.md` |
| How is the repo laid out across packages? | `09_repo_structure.md` |
| How does edge-lite work right now? | `10_edge.md`, `11_edge_lite_feasibility.md` |
| What do quick-start readers see first? | `../README.md`, `../backend/README.md`, `../frontend/README.md`, `../edge/README.md` |

## Conventions

- Document implemented behavior first; if something is aspirational, label it clearly.
- `openapi.yaml` is the API schema source of truth; keep markdown API docs aligned with it.
- `../AGENTS.md` governs repo coordination; `docs/AGENTS.md` governs spec accuracy and maintenance.
- Keep backend `GET /health` separate from edge `GET /healthz`.
- Default database language must match code: PostgreSQL is the only supported backend database.
- Frontend form guidance must match current code (`useState`) unless implementation changes.
- Auth and ingest docs must preserve verified-email gating where the current backend enforces it.
- Edge docs must describe the current KV snapshot shape and current `token_hash` auth caveat exactly as implemented.
- Batch delete is synchronous in the current backend; do not document it as queued or async.

## Anti-Patterns

- Do not describe Herald as Bark-only or raw-text ingest.
- Do not reintroduce EdgeOne/proxy-mode language for the current edge package.
- Do not claim `react-hook-form` or `zod` power the current UI.
- Do not state that same-origin deployment is required when the app uses direct browser-to-backend calls plus CORS.
- Do not hide dashed UUID ingest support or the edge-lite `token_hash` comparison behavior.
- Do not document batch delete as asynchronous unless the backend implementation changes.
