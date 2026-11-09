# Herald backend

Python 3.13+ FastAPI service with a standard-library SQLite store and an in-process delivery worker. Run from the repository root:

```bash
uv sync --project backend --locked
uv run --project backend --locked herald-backend
uv run --project backend --locked pytest backend/tests -q
```

Startup creates the schema and private credentials in `HERALD_DATA_DIR` (default `./data`), obtains a process lock, recovers interrupted deliveries, and starts bounded provider dispatch. There is no separate migration or worker command. `herald-backend init` creates credentials without starting HTTP.

Build `frontend/dist` to serve the dashboard from the API. See [Operations](../docs/07_operations.md) for configuration and durable backup, and [API](../docs/04_api_spec.md) for the send contract.
