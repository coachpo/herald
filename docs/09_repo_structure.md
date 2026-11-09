# Repo Structure

```text
herald/
├── backend/                 # FastAPI backend, migrations, worker
├── frontend/                # React/Vite dashboard
├── edge/
│   ├── shared/              # relay protocol helpers
│   ├── cloudflare/          # Worker + Durable Object
│   ├── edgeone/             # Pages function + build helper
│   └── tests/               # node:test suite
├── docs/                    # markdown specs + OpenAPI
├── scripts/                 # sync/backup/version helpers
├── docker-compose.yml       # production compose
├── docker-compose.dev.yml   # development compose
└── start.sh                 # local helper
```

## Boundaries

- Backend owns durable storage, rule semantics, provider dispatch, and machine config export.
- Frontend owns browser UX only.
- Edge owns ingress relay behavior only.

## Startup

- `docker compose up` runs production-posture backend services after the required environment variables have been configured.
- `docker compose -f docker-compose.dev.yml up` runs `db`, `migrate`, `api`, and `worker`; it does not run Vite.
- `./start.sh full` runs local PostgreSQL, the backend API, and Vite with helper ports; `headless` omits Vite. Neither mode starts the delivery worker.

Use [Operations](07_operations.md) for startup prerequisites, port ownership, environment configuration, and the separate worker command. Frontend-only setup is in the [frontend README](../frontend/README.md).

## Development principles

These are the shared design and development defaults, not claims about a deployment's capacity or permission to remove existing safeguards.

- When platform capabilities, resource tiers, or quotas are uncertain, implement against the looser supported option and record it as a working assumption. Revisit when authoritative platform documentation, an observed limit, or an accepted requirement establishes a tighter constraint; do not present an assumed quota as measured behavior.
- Assume the overwhelming majority of requests are legitimate. Do not add preemptive abuse handling, conservative rate limits, or adversarial hardening beyond accepted requirements. Revisit when concrete operational evidence or an explicitly accepted security/product requirement calls for it.
- Choose the best-case path by default. Treat worst-case handling as a named decision with its triggering evidence or requirement, not inherited caution. Preserve the existing SSRF checks, authentication, encryption, redaction, configured limits, and other obligations in [Security and Privacy](06_security_privacy.md).
- Keep source files cohesive, navigable, and reviewable. When growth mixes responsibilities, hides important behavior, or makes focused changes difficult to review, split by cohesive responsibility within the task's scope. Follow established project size limits; where none exist, use those concrete symptoms rather than a universal line-count cap. Do not introduce fragments or abstractions merely to shorten files.
