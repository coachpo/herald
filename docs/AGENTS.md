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
| Where do test and verification expectations live? | `../backend/AGENTS.md`, `../frontend/AGENTS.md`, `../edge/AGENTS.md`, `07_operations.md` |
| What do quick-start readers see first? | `../README.md`, `../backend/README.md`, `../frontend/README.md`, `../edge/README.md` |

## Conventions

- Document implemented behavior first; if something is aspirational, label it clearly.
- `openapi.yaml` is the API schema source of truth; keep markdown API docs aligned with it.
- `../AGENTS.md` governs repo coordination; `docs/AGENTS.md` governs spec accuracy and maintenance.
- Keep backend `GET /health` separate from edge `GET /healthz`; backend health returns `200` when the database is connected and `503` with `status: degraded` when it is not.
- Verified email is currently required for backend ingest; the shipped frontend also disables common mutating dashboard flows for unverified users. Do not invent `REQUIRE_VERIFIED_EMAIL_FOR_INGEST` or claim universal backend write gating unless the code changes.
- Message list docs should only promise the filters the backend actually honors today: `ingest_endpoint_id`, `priority_min`, `priority_max`, `from`, and `to`.
- Channels support list/create/delete/test only; channel creation responses return `{channel, config}`.
- `GET /api/ingest-endpoints/{endpoint_id}` and `PATCH /api/ingest-endpoints/{endpoint_id}` exist in the backend even if older prose omitted them.
- Verification and password-reset request endpoints create hashed tokens and log events; do not describe repo-local email delivery that the code does not implement.
- Edge docs must describe the current KV snapshot shape and current `token_hash` auth caveat exactly as implemented.
- Only MQTT exposes an SSRF/private-network env toggle; Bark, ntfy, and Gotify use default blocking in code.
- Batch delete is synchronous in the current backend; do not document it as queued or async.

## Anti-Patterns

- Do not describe Herald as Bark-only or raw-text ingest.
- Do not reintroduce EdgeOne/proxy-mode language for the current edge package.
- Do not claim `react-hook-form` or `zod` power the current UI.
- Do not state that same-origin deployment is required when the app uses direct browser-to-backend calls plus CORS.
- Do not hide dashed UUID ingest support or the edge-lite `token_hash` comparison behavior.
- Do not document batch delete as asynchronous unless the backend implementation changes.
- Do not claim `q`, `group`, or `tag` message filters, deleted channel detail/update routes, or repo-local verification/reset emails unless the code changes.
- Do not mention non-existent auth/ingest env toggles or per-provider SSRF toggles beyond MQTT.
