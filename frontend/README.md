# Herald dashboard

A small React interface for a single operator: configure Bark, ntfy, MQTT, or Gotify targets; submit messages; inspect asynchronous delivery results; and retry failed deliveries.

Use the management token from the server's private `credentials.env` file to connect. It stays in this browser tab's session storage. The separate ingest token is never returned by the dashboard API. Outlet credentials are encrypted on the server, omitted from read responses, and preserved when an edit leaves their fields blank.

From the repository root, with Node 24 and pnpm 10.30.1:

```bash
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend dev
```

Vite runs on port 3000 and proxies API requests to port 8000. Start the backend separately; its embedded worker processes deliveries. There is no `VITE_API_URL` or frontend environment configuration.

For production, build the UI and let the backend serve `frontend/dist` from the same origin:

```bash
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
```

There is no independent Node static server or frontend container. The backend serves the built page and API in one process. See [Operations](../docs/07_operations.md) for server startup and credential handling.

An accepted message is durably stored and queued, not yet delivered. The history shows each target's status and error. Manual retry is available only for failed deliveries; successful deliveries cannot be replayed. Cleanup removes only fully sent history older than the configured retention period and retains pending or failed work.
