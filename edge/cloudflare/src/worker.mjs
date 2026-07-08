import { jsonResponse, bearerToken } from "../../shared/http.mjs";
import { authenticateIngest, timingSafeEqualStrings } from "../../shared/auth.mjs";
import { parseIngestEndpointIdFromPath, validatePayload } from "../../shared/validate.mjs";
import {
  buildEnvelope,
  parseRelayHeaders,
  forwardEnvelope,
  backoffSeconds,
  MAX_PENDING_AGE_MS,
} from "../../shared/relay.mjs";
import { makeConfigLoader } from "../../shared/config-cache.mjs";

const MAX_BODY_BYTES = 1024 * 1024;
let configLoader = null;

function getConfigLoader(env) {
  if (!configLoader) {
    configLoader = makeConfigLoader(() => env.EDGE_CONFIG.get("config", "json"));
  }
  return configLoader;
}

async function requireAdmin(request, env) {
  if (!env.RELAY_ADMIN_TOKEN) return false;
  return timingSafeEqualStrings(bearerToken(request), env.RELAY_ADMIN_TOKEN);
}

async function handleIngest(request, env, url) {
  const endpointId = parseIngestEndpointIdFromPath(url.pathname);
  if (!endpointId) return jsonResponse({ code: "not_found", message: "not found" }, 404);
  if (request.method !== "POST") {
    return jsonResponse({ code: "method_not_allowed", message: "method not allowed" }, 405);
  }
  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonResponse({ code: "unsupported_media_type", message: "Content-Type must be application/json" }, 415);
  }

  const config = await getConfigLoader(env)();
  if (!config) return jsonResponse({ code: "misconfigured", message: "edge config not loaded" }, 500);

  const rawKey = request.headers.get("X-Herald-Ingest-Key") || "";
  const endpoint = await authenticateIngest(config, endpointId, rawKey);
  if (!endpoint) return jsonResponse({ code: "not_authenticated", message: "unauthorized" }, 401);

  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) {
    return jsonResponse({ code: "payload_too_large", message: "max 1MB" }, 413);
  }
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
  }
  const validation = validatePayload(parsed);
  if (!validation.ok) {
    return jsonResponse({ code: "validation_error", message: validation.error }, 422);
  }

  const relay = parseRelayHeaders(request);
  const via = relay.via ? `${relay.via},cloudflare` : "cloudflare";
  const envelope = buildEnvelope({
    endpointId: endpoint.id,
    rawKey: rawKey.trim(),
    body,
    via,
    nowIso: new Date().toISOString(),
    id: relay.id,
    receivedAt: relay.receivedAt,
  });

  const stub = env.RELAY_BUFFER.get(env.RELAY_BUFFER.idFromName("global"));
  const res = await stub.fetch("https://do/enqueue", {
    method: "POST",
    body: JSON.stringify(envelope),
  });
  if (!res.ok) return jsonResponse({ code: "buffer_error", message: "enqueue failed" }, 500);
  return jsonResponse({ message_id: envelope.id, status: "relayed" }, 202);
}

export async function handleRequest(request, env) {
  const url = new URL(request.url);
  if (url.pathname === "/healthz") {
    return jsonResponse({ ok: true, mode: "relay", platform: "cloudflare" }, 200);
  }
  if (url.pathname === "/admin/config" && request.method === "POST") {
    if (!(await requireAdmin(request, env))) return jsonResponse({ code: "forbidden" }, 403);
    const body = await request.text();
    try {
      JSON.parse(body);
    } catch {
      return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
    }
    await env.EDGE_CONFIG.put("config", body);
    configLoader = null;
    return jsonResponse({ ok: true }, 200);
  }
  if (url.pathname === "/admin/status" || url.pathname === "/relay/drain") {
    if (!(await requireAdmin(request, env))) return jsonResponse({ code: "forbidden" }, 403);
    const stub = env.RELAY_BUFFER.get(env.RELAY_BUFFER.idFromName("global"));
    if (url.pathname === "/relay/drain") {
      if (request.method !== "POST") return jsonResponse({ code: "method_not_allowed" }, 405);
      return stub.fetch("https://do/drain", { method: "POST" });
    }
    const doStatus = await (await stub.fetch("https://do/status")).json();
    const config = await getConfigLoader(env)();
    return jsonResponse({ ...doStatus, config_version: config?.version ?? null }, 200);
  }
  return handleIngest(request, env, url);
}

export default {
  async fetch(request, env) {
    return handleRequest(request, env);
  },
};

export class RelayBuffer {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS pending (" +
        "id TEXT PRIMARY KEY, endpoint_id TEXT NOT NULL, received_at TEXT NOT NULL, " +
        "via TEXT NOT NULL, ingest_key TEXT NOT NULL, body TEXT NOT NULL, " +
        "attempts INTEGER NOT NULL DEFAULT 0, next_attempt_ms INTEGER NOT NULL, " +
        "last_error TEXT, created_ms INTEGER NOT NULL)",
    );
    ctx.storage.sql.exec(
      "CREATE TABLE IF NOT EXISTS dead (" +
        "id TEXT PRIMARY KEY, envelope TEXT NOT NULL, reason TEXT, died_ms INTEGER NOT NULL)",
    );
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/enqueue" && request.method === "POST") {
      const e = await request.json();
      const now = Date.now();
      this.ctx.storage.sql.exec(
        "INSERT OR IGNORE INTO pending (id, endpoint_id, received_at, via, ingest_key, body, attempts, next_attempt_ms, last_error, created_ms) " +
          "VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)",
        e.id,
        e.endpoint_id,
        e.received_at,
        e.via,
        e.ingest_key,
        e.body,
        now,
        now,
      );
      await this.ctx.storage.setAlarm(now);
      return Response.json({ ok: true });
    }
    if (url.pathname === "/drain" && request.method === "POST") {
      return Response.json(await this.drainDue(true));
    }
    if (url.pathname === "/status") {
      const p = this.ctx.storage.sql
        .exec("SELECT COUNT(*) AS n, MIN(created_ms) AS oldest FROM pending").one();
      const d = this.ctx.storage.sql.exec("SELECT COUNT(*) AS n FROM dead").one();
      return Response.json({
        pending: p.n,
        dead: d.n,
        oldest_pending_at: p.oldest ? new Date(p.oldest).toISOString() : null,
      });
    }
    return Response.json({ error: "not_found" }, { status: 404 });
  }

  async alarm() {
    await this.drainDue();
  }

  async forward(id, nowMs = Date.now()) {
    const cursor = this.ctx.storage.sql.exec("SELECT * FROM pending WHERE id = ?", id);
    const rows = cursor.toArray();
    if (!rows.length) return { ok: true };
    const row = rows[0];
    if (nowMs - row.created_ms > MAX_PENDING_AGE_MS) {
      this._kill(row, "max_age_exceeded");
      return { ok: false };
    }
    const result = await forwardEnvelope(row, this.env.UPSTREAM_URL);
    if (result.ok) {
      this.ctx.storage.sql.exec("DELETE FROM pending WHERE id = ?", row.id);
    } else if (result.permanent) {
      this._kill(row, result.error);
    } else {
      const attempts = row.attempts + 1;
      this.ctx.storage.sql.exec(
        "UPDATE pending SET attempts = ?, next_attempt_ms = ?, last_error = ? WHERE id = ?",
        attempts,
        nowMs + backoffSeconds(attempts) * 1000,
        result.error,
        row.id,
      );
    }
    return { ok: result.ok };
  }

  async drainDue(force = false) {
    const now = Date.now();
    const rows = this.ctx.storage.sql
      .exec(
        force
          ? "SELECT id FROM pending ORDER BY created_ms LIMIT 25"
          : "SELECT id FROM pending WHERE next_attempt_ms <= ? ORDER BY created_ms LIMIT 25",
        ...(force ? [] : [now]),
      )
      .toArray();
    let drained = 0;
    let failed = 0;
    for (const { id } of rows) {
      const result = await this.forward(id, now);
      if (result.ok) drained++;
      else failed++;
    }
    this.ctx.storage.sql.exec("DELETE FROM dead WHERE died_ms < ?", now - 30 * 24 * 3600 * 1000);
    await this.rearmAlarm(now);
    const dead = this.ctx.storage.sql.exec("SELECT COUNT(*) AS n FROM dead").one().n;
    return { drained, failed, dead };
  }

  async rearmAlarm(nowMs) {
    const next = this.ctx.storage.sql
      .exec("SELECT MIN(next_attempt_ms) AS ts FROM pending").one();
    if (next.ts != null) await this.ctx.storage.setAlarm(Math.max(next.ts, nowMs + 1000));
  }

  _kill(row, reason) {
    this.ctx.storage.sql.exec(
      "INSERT OR REPLACE INTO dead (id, envelope, reason, died_ms) VALUES (?, ?, ?, ?)",
      row.id,
      JSON.stringify({ ...row, ingest_key: "[redacted]" }),
      reason,
      Date.now(),
    );
    this.ctx.storage.sql.exec("DELETE FROM pending WHERE id = ?", row.id);
  }
}
