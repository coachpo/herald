# docs/AGENTS.md

## Documentation Boundaries

- Use the [root documentation index](../README.md#docs) for document ownership. Preserve intentional translations and link shared facts instead of copying whole policies.
- Describe implemented behavior from source/config/tests; label requirements, proposals, and unverified facts separately. Repository files do not establish actual deployment, users, or retention obligations.
- Pair workflow commands with working directory, prerequisites, responsible operator, and exceptions that change the next action. Keep secrets out of examples.
- `openapi.yaml` is a generated FastAPI schema snapshot (JSON syntax is valid YAML). Do not hand-edit it. There is no checked-in generator/checker; use `create_app().openapi()` as the generation source, with a valid dummy PostgreSQL `DATABASE_URL` and development settings, without starting a server or connecting to the database. Review generated changes separately.
- OpenAPI does not capture manually parsed ingest bodies, all error/status behavior, or provider config constraints. Maintain those contracts in [the human API guide](04_api_spec.md).
- No dedicated documentation checker is configured in CI. For prose changes, check affected local links/anchors, source facts, and `git diff --check`; do not run unrelated full suites or regenerate artifacts merely for wording edits.
