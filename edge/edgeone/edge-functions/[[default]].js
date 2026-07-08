import { jsonResponse, bearerToken } from "./_shared/http.mjs";
import { authenticateIngest } from "./_shared/auth.mjs";
import { parseIngestEndpointIdFromPath, validatePayload } from "./_shared/validate.mjs";
import {
  buildEnvelope,
  parseRelayHeaders,
  forwardEnvelope,
  backoffSeconds,
  MAX_PENDING_AGE_MS,
} from "./_shared/relay.mjs";
import { makeConfigLoader } from "./_shared/config-cache.mjs";

const MAX_BODY_BYTES = 1024 * 1024;
const DRAIN_BATCH = 20;
const DEAD_RETENTION_MS = 30 * 24 * 3600 * 1000;
let configLoader = null;

function kvBinding() {
  return globalThis.EDGE_CONFIG;
}

function getConfigLoader() {
  if (!configLoader) {
    configLoader = makeConfigLoader(async () => {
      const raw = await kvBinding().get("config", { type: "json" });
      return raw || null;
    });
  }
  return configLoader;
}

function pendingKey(envelope) {
  const ts = String(envelope.created_ms).padStart(16, "0");
  return `p_${ts}_${envelope.id.replace(/-/g, "")}`;
}

function msFromKey(key) {
  return Number(key.slice(2, 18));
}

async function purgeExpiredDead(kv, nowMs) {
  const listed = await kv.list({ prefix: "d_", limit: 50 });
  for (const k of listed?.keys || []) {
    const key = k.key ?? k.name ?? k;
    if (nowMs - msFromKey(key) > DEAD_RETENTION_MS) await kv.delete(key);
  }
}

async function saveOutcome(kv, key, envelope, outcome, now) {
  if (outcome.ok) {
    await kv.delete(key);
    return "drained";
  }
  if (outcome.permanent) {
    await kv.put(
      `d_${key.slice(2)}`,
      JSON.stringify({ ...envelope, ingest_key: "[redacted]", last_error: outcome.error }),
    );
    await kv.delete(key);
    return "dead";
  }
  const attempts = (envelope.attempts || 0) + 1;
  await kv.put(key, JSON.stringify({
    ...envelope,
    attempts,
    last_error: outcome.error,
    next_attempt_ms: now + backoffSeconds(attempts) * 1000,
  }));
  return "failed";
}

export async function drainPending(env, limit, skipKey = null) {
  const kv = kvBinding();
  const listed = await kv.list({ prefix: "p_", limit });
  const keys = (listed?.keys || []).map((k) => k.key ?? k.name ?? k);
  let drained = 0;
  let failed = 0;
  let dead = 0;
  const now = Date.now();
  for (const key of keys) {
    if (key === skipKey) continue;
    const envelope = await kv.get(key, { type: "json" });
    if (!envelope) continue;
    const createdMs = envelope.created_ms || msFromKey(key);
    let outcome;
    if (now - createdMs > MAX_PENDING_AGE_MS) {
      outcome = { ok: false, permanent: true, error: "max_age_exceeded" };
    } else if (envelope.next_attempt_ms && envelope.next_attempt_ms > now) {
      continue;
    } else {
      outcome = await forwardEnvelope(envelope, env.UPSTREAM_URL);
    }
    const saved = await saveOutcome(kv, key, envelope, outcome, now);
    if (saved === "drained") {
      drained++;
    } else if (saved === "dead") {
      dead++;
    } else {
      failed++;
    }
  }
  await purgeExpiredDead(kv, now);
  return { drained, failed, dead };
}

async function handleIngest(request, env, url, waitUntil) {
  const endpointId = parseIngestEndpointIdFromPath(url.pathname);
  if (!endpointId) return jsonResponse({ code: "not_found", message: "not found" }, 404);
  if (request.method !== "POST") {
    return jsonResponse({ code: "method_not_allowed", message: "method not allowed" }, 405);
  }
  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonResponse({ code: "unsupported_media_type", message: "Content-Type must be application/json" }, 415);
  }
  const config = await getConfigLoader()();
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
  const via = relay.via ? `${relay.via},edgeone` : "edgeone";
  const envelope = buildEnvelope({
    endpointId: endpoint.id,
    rawKey: rawKey.trim(),
    body,
    via,
    nowIso: new Date().toISOString(),
    id: relay.id,
    receivedAt: relay.receivedAt,
  });
  envelope.created_ms = Date.now();

  const key = pendingKey(envelope);
  await kvBinding().put(key, JSON.stringify(envelope));

  waitUntil((async () => {
    const result = await forwardEnvelope(envelope, env.UPSTREAM_URL);
    await saveOutcome(kvBinding(), key, envelope, result, Date.now());
    await drainPending(env, 3, key);
  })());

  return jsonResponse({ message_id: envelope.id, status: "relayed" }, 202);
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const waitUntil = (p) => context.waitUntil(p);

  if (url.pathname === "/healthz") {
    return jsonResponse({ ok: true, mode: "relay", platform: "edgeone" }, 200);
  }
  const isAdmin = url.pathname === "/admin/config" || url.pathname === "/admin/status" ||
    url.pathname === "/relay/drain";
  if (isAdmin) {
    if (!env.RELAY_ADMIN_TOKEN || bearerToken(request) !== env.RELAY_ADMIN_TOKEN) {
      return jsonResponse({ code: "forbidden" }, 403);
    }
    if (url.pathname === "/admin/config" && request.method === "POST") {
      const body = await request.text();
      try {
        JSON.parse(body);
      } catch {
        return jsonResponse({ code: "bad_request", message: "invalid JSON" }, 400);
      }
      await kvBinding().put("config", body);
      configLoader = null;
      return jsonResponse({ ok: true }, 200);
    }
    if (url.pathname === "/relay/drain" && request.method === "POST") {
      return jsonResponse(await drainPending(env, DRAIN_BATCH), 200);
    }
    if (url.pathname === "/admin/status") {
      const pending = await kvBinding().list({ prefix: "p_", limit: 256 });
      const deadKeys = await kvBinding().list({ prefix: "d_", limit: 256 });
      const config = await getConfigLoader()();
      const pendingKeys = (pending?.keys || []).map((k) => k.key ?? k.name ?? k);
      return jsonResponse({
        pending: pendingKeys.length,
        dead: (deadKeys?.keys || []).length,
        config_version: config?.version ?? null,
        oldest_pending_at: pendingKeys.length
          ? new Date(msFromKey(pendingKeys[0])).toISOString()
          : null,
      }, 200);
    }
    return jsonResponse({ code: "method_not_allowed" }, 405);
  }
  return handleIngest(request, env, url, waitUntil);
}
