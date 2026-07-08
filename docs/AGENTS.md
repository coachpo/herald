# docs/AGENTS.md

## Overview

Documentation is expected to describe the implemented system. `docs/openapi.yaml` is generated from the FastAPI app and should stay aligned with routes.

## Index

- `01_prd.md`: product scope
- `02_architecture.md`: runtime topology
- `03_data_model.md`: database tables
- `04_api_spec.md`: human API guide
- `05_ui_spec.md`: frontend routes and screens
- `06_security_privacy.md`: keys, auth, safety
- `07_operations.md`: deployment and operations
- `08_bark_v2.md`: Bark provider details
- `09_repo_structure.md`: package boundaries
- `10_edge.md`: Cloudflare and EdgeOne relay protocol
- `14_production_upgrade_verification.md`: verification evidence for the production upgrade
- `openapi.yaml`: generated OpenAPI schema

## Rules

- Keep command examples paired with working directory and service scope.
- Keep docs accurate to the current code, not older plans.
- Do not document unimplemented filters, providers, or UI routes.
- Do not include raw secrets in examples.
