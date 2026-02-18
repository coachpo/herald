# Edge Forwarders (EdgeOne + Cloudflare)

> **v1.0 note:** The ingest API now requires `Content-Type: application/json` with a structured JSON body. Edge forwarders forward the body as-is without parsing or validating the JSON payload — all validation happens at the backend. No edge code changes are required for the v1.0 upgrade.

This project can optionally run edge forwarding functions in front of the backend Ingest API.

Goals:

- Keep the request shape identical to the backend Ingest API.
- Allow multi-hop routing across edge providers.
- Use per-hop authentication keys.

## Request Shape

Edge functions accept:

- `POST /api/ingest/{endpoint_id}`
  - header: `X-Beacon-Ingest-Key: <edge_ingest_key>`
  - body: JSON payload (forwarded as-is; validated by backend)

They forward to a configured next hop:

- `UPSTREAM_INGEST_URL` (a full URL to the next hop's `/api/ingest/{endpoint_id}`)
- `UPSTREAM_INGEST_KEY` (the key used for the next hop)

The function replaces the incoming `X-Beacon-Ingest-Key` with `UPSTREAM_INGEST_KEY`.

The edge function also preserves the incoming query string by appending it to the configured upstream ingest URL.

## Configuration

Each hop is configured independently with:

- Incoming authentication (the key(s) clients / previous hop must send)
  - `EDGE_INGEST_KEYS` (comma-separated)
  - EdgeOne-safe variant (no `_`): `EDGE-INGEST-KEYS`
- Optional endpoint pinning (rejects requests for other endpoint ids)
  - `EDGE_EXPECT_ENDPOINT_ID`
  - EdgeOne-safe variant: `EDGE-EXPECT-ENDPOINT-ID`
- Next hop ingest destination
  - Preferred: `UPSTREAM_INGEST_URL` (full URL to `/api/ingest/{endpoint_id}`)
  - EdgeOne-safe variant: `UPSTREAM-INGEST-URL`
  - Alternative (construct full ingest URL): `UPSTREAM_BASE_URL` + `UPSTREAM_ENDPOINT_ID`
- Next hop authentication
  - `UPSTREAM_INGEST_KEY`
  - EdgeOne-safe variant: `UPSTREAM-INGEST-KEY`
- Loop safety
  - `EDGE_MAX_HOPS` (default: 5)
  - EdgeOne-safe variant: `EDGE-MAX-HOPS`
- Optional observability
  - `EDGE_NAME` / `EDGE-NAME` (sets `X-Beacon-Edge-Name`)

## Supported Routing Paths

Examples:

- Request -> EdgeOne -> Cloudflare -> Ingestion
- Request -> EdgeOne -> Ingestion
- Request -> Cloudflare -> Ingestion
- Request -> Cloudflare -> EdgeOne -> Ingestion

## Multi-hop Examples

### Request -> Cloudflare -> Ingestion

Cloudflare worker configuration:

```
EDGE_INGEST_KEYS=edge-cf-key
UPSTREAM_INGEST_URL=https://api.example.com/api/ingest/<endpoint_id>
UPSTREAM_INGEST_KEY=<backend_ingest_key>
EDGE_NAME=cloudflare
```

Client request:

```
POST https://edge-cf.example.com/api/ingest/<endpoint_id>
X-Beacon-Ingest-Key: edge-cf-key

<raw utf-8 body>
```

### Request -> EdgeOne -> Cloudflare -> Ingestion

EdgeOne forwarder configuration (forwards *into* the Cloudflare worker):

```
EDGE-INGEST-KEYS=edge-eo-key
UPSTREAM-INGEST-URL=https://edge-cf.example.com/api/ingest/<endpoint_id>
UPSTREAM-INGEST-KEY=edge-cf-key
EDGE-NAME=edgeone
```

Cloudflare forwarder configuration (forwards *into* the backend ingest API):

```
EDGE_INGEST_KEYS=edge-cf-key
UPSTREAM_INGEST_URL=https://api.example.com/api/ingest/<endpoint_id>
UPSTREAM_INGEST_KEY=<backend_ingest_key>
EDGE_NAME=cloudflare
```

Client request (into EdgeOne):

```
POST https://edge-eo.example.com/api/ingest/<endpoint_id>
X-Beacon-Ingest-Key: edge-eo-key

<raw utf-8 body>
```

## Loop Safety

Edge functions add `X-Beacon-Edge-Hop: <n>` and enforce `EDGE_MAX_HOPS`.

If the hop limit is exceeded, the edge function rejects the request with HTTP 508.

## Observability Headers

Edge forwarders may add:

- `X-Beacon-Edge-Name`
- `X-Beacon-Edge-Client-IP`
- `X-Forwarded-For`

Note: the backend currently records the upstream remote IP from the socket (`REMOTE_ADDR`). These headers are best-effort and primarily for debugging.

## Submodule

Implementation lives in the `edge/` git submodule.
