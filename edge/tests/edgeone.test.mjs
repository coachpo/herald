import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../shared/auth.mjs";
import { drainPending, onRequest } from "../edgeone/edge-functions/[[default]].js";

class MemoryKV {
  constructor() {
    this.map = new Map();
  }
  async get(key, opts) {
    const value = this.map.get(key);
    if (value == null) return null;
    return opts?.type === "json" ? JSON.parse(value) : value;
  }
  async put(key, value) {
    this.map.set(key, typeof value === "string" ? value : JSON.stringify(value));
  }
  async delete(key) {
    this.map.delete(key);
  }
  async list({ prefix = "", limit = 256, cursor = null } = {}) {
    const all = [...this.map.keys()].filter((key) => key.startsWith(prefix)).sort();
    const start = cursor ? Number(cursor) : 0;
    const page = all.slice(start, start + limit);
    const next = start + page.length;
    return {
      keys: page.map((key) => ({ key })),
      complete: next >= all.length,
      cursor: next < all.length ? String(next) : undefined,
    };
  }
}

function context(request) {
  const waits = [];
  return {
    waits,
    ctx: {
      request,
      env: { RELAY_ADMIN_TOKEN: "admin", UPSTREAM_URL: "https://cf.example.com" },
      waitUntil: (p) => waits.push(p),
    },
  };
}

async function writeConfig(key = "raw-key", version = "v1") {
  const endpoint = {
    id: "550e8400-e29b-41d4-a716-446655440000",
    key_sha256: await sha256Hex(key),
  };
  const { ctx } = context(new Request("https://edge/admin/config", {
    method: "POST",
    headers: { Authorization: "Bearer admin" },
    body: JSON.stringify({ version, ingest_endpoints: [endpoint] }),
  }));
  assert.equal((await onRequest(ctx)).status, 200);
  return endpoint;
}

test.beforeEach(() => {
  globalThis.EDGE_CONFIG = new MemoryKV();
});

test.afterEach(() => {
  delete globalThis.EDGE_CONFIG;
  delete globalThis.fetch;
});

test("healthz and admin auth", async () => {
  const ok = await onRequest(context(new Request("https://edge/healthz")).ctx);
  assert.equal(ok.status, 200);
  assert.deepEqual(await ok.json(), { ok: true, mode: "relay", platform: "edgeone" });
  const forbidden = await onRequest(context(new Request("https://edge/admin/status")).ctx);
  assert.equal(forbidden.status, 403);
});

test("admin status reports config cache ttl and oldest pending", async () => {
  const realNow = Date.now;
  let now = 1_000;
  Date.now = () => now;
  try {
    await writeConfig("raw-key", "v1");
    await globalThis.EDGE_CONFIG.put(`p_${String(now).padStart(16, "0")}_oldest`, JSON.stringify({
      id: "oldest",
      endpoint_id: "550e8400-e29b-41d4-a716-446655440000",
      received_at: new Date(now).toISOString(),
      via: "edgeone",
      ingest_key: "raw-key",
      body: "{}",
      created_ms: now,
    }));

    const status1 = await onRequest(context(new Request("https://edge/admin/status", {
      headers: { Authorization: "Bearer admin" },
    })).ctx);
    assert.deepEqual(await status1.json(), {
      pending: 1,
      dead: 0,
      config_version: "v1",
      oldest_pending_at: new Date(now).toISOString(),
      truncated: false,
    });

    await globalThis.EDGE_CONFIG.put("config", JSON.stringify({ version: "v2", ingest_endpoints: [] }));
    now += 50_000;
    const cached = await onRequest(context(new Request("https://edge/admin/status", {
      headers: { Authorization: "Bearer admin" },
    })).ctx);
    assert.equal((await cached.json()).config_version, "v1");

    now += 11_000;
    const refreshed = await onRequest(context(new Request("https://edge/admin/status", {
      headers: { Authorization: "Bearer admin" },
    })).ctx);
    assert.equal((await refreshed.json()).config_version, "v2");
  } finally {
    Date.now = realNow;
  }
});

test("ingest stores pending then waitUntil successful forward deletes it", async () => {
  const endpoint = await writeConfig();
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response("ok", { status: 202 });
  };
  const { ctx, waits } = context(new Request(`https://edge/api/ingest/${endpoint.id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Herald-Ingest-Key": "raw-key" },
    body: JSON.stringify({ body: "hello" }),
  }));
  const res = await onRequest(ctx);
  assert.equal(res.status, 202);
  assert.equal(waits.length, 1);
  await Promise.all(waits);
  assert.equal(calls.length, 1);
  assert.equal((await globalThis.EDGE_CONFIG.list({ prefix: "p_" })).keys.length, 0);
});

test("waitUntil 5xx keeps pending with retry metadata", async () => {
  const endpoint = await writeConfig();
  globalThis.fetch = async () => new Response("bad", { status: 500 });
  const { ctx, waits } = context(new Request(`https://edge/api/ingest/${endpoint.id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Herald-Ingest-Key": "raw-key" },
    body: JSON.stringify({ body: "hello" }),
  }));
  assert.equal((await onRequest(ctx)).status, 202);
  await Promise.all(waits);
  const [item] = (await globalThis.EDGE_CONFIG.list({ prefix: "p_" })).keys;
  const envelope = await globalThis.EDGE_CONFIG.get(item.key, { type: "json" });
  assert.equal(envelope.attempts, 1);
  assert.ok(envelope.next_attempt_ms > Date.now());
});

test("drain moves permanent failures to dead and purges old dead", async () => {
  const endpoint = await writeConfig();
  const old = String(Date.now() - 31 * 24 * 3600 * 1000).padStart(16, "0");
  await globalThis.EDGE_CONFIG.put(`d_${old}_old`, "{}");
  await globalThis.EDGE_CONFIG.put(`p_${String(Date.now()).padStart(16, "0")}_x`, JSON.stringify({
    id: "x",
    endpoint_id: endpoint.id,
    received_at: new Date().toISOString(),
    via: "edgeone",
    ingest_key: "raw-key",
    body: "{}",
    created_ms: Date.now(),
  }));
  globalThis.fetch = async () => new Response("bad", { status: 422 });
  const res = await onRequest(context(new Request("https://edge/relay/drain", {
    method: "POST",
    headers: { Authorization: "Bearer admin" },
  })).ctx);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.dead, 1);
  assert.equal((await globalThis.EDGE_CONFIG.list({ prefix: "d_" })).keys.length, 1);
});

test("drain succeeds then empty drain is no-op", async () => {
  const endpoint = await writeConfig();
  for (const id of ["a", "b"]) {
    await globalThis.EDGE_CONFIG.put(`p_${String(Date.now()).padStart(16, "0")}_${id}`, JSON.stringify({
      id,
      endpoint_id: endpoint.id,
      received_at: new Date().toISOString(),
      via: "edgeone",
      ingest_key: "raw-key",
      body: "{}",
      created_ms: Date.now(),
    }));
  }
  globalThis.fetch = async () => new Response("ok", { status: 201 });
  const request = new Request("https://edge/relay/drain", {
    method: "POST",
    headers: { Authorization: "Bearer admin" },
  });
  const drained = await onRequest(context(request).ctx);
  assert.deepEqual(await drained.json(), { drained: 2, failed: 0, dead: 0 });
  assert.equal((await globalThis.EDGE_CONFIG.list({ prefix: "p_" })).keys.length, 0);

  const empty = await onRequest(context(request).ctx);
  assert.deepEqual(await empty.json(), { drained: 0, failed: 0, dead: 0 });
});

function makeEnvelope({ id, createdMs, nextAttemptMs = null }) {
  return {
    id,
    endpoint_id: id,
    received_at: new Date(createdMs).toISOString(),
    via: "edgeone",
    ingest_key: "k",
    body: JSON.stringify({ body: "x" }),
    attempts: 0,
    last_error: null,
    created_ms: createdMs,
    ...(nextAttemptMs ? { next_attempt_ms: nextAttemptMs } : {}),
  };
}

function pendingKeyOf(envelope) {
  return `p_${String(envelope.created_ms).padStart(16, "0")}_${envelope.id.replace(/-/g, "")}`;
}

function uid(i) {
  return `${String(i).padStart(8, "0")}-0000-4000-8000-000000000000`;
}

function stubFetch(status = 200) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response("{}", { status });
  };
  return calls;
}

test("drain skips backoff keys without head-of-line blocking (cross-page)", async () => {
  const base = Date.now();
  const future = base + 3600_000;
  for (let i = 0; i < 120; i++) {
    const envelope = makeEnvelope({
      id: uid(i),
      createdMs: base - 10_000 + i,
      nextAttemptMs: future,
    });
    await globalThis.EDGE_CONFIG.put(pendingKeyOf(envelope), JSON.stringify(envelope));
  }
  const eligible = makeEnvelope({ id: uid(200), createdMs: base - 5_000 });
  await globalThis.EDGE_CONFIG.put(pendingKeyOf(eligible), JSON.stringify(eligible));
  const calls = stubFetch(200);
  const result = await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 20 });
  assert.equal(result.drained, 1);
  assert.equal(calls.length, 1);
  assert.equal(result.failed, 0);
});

test("force drain retries keys still in backoff", async () => {
  const envelope = makeEnvelope({
    id: uid(1),
    createdMs: Date.now() - 1000,
    nextAttemptMs: Date.now() + 3600_000,
  });
  await globalThis.EDGE_CONFIG.put(pendingKeyOf(envelope), JSON.stringify(envelope));
  const calls = stubFetch(200);
  const result = await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 20, force: true });
  assert.equal(result.drained, 1);
  assert.equal(calls.length, 1);
});

test("dead keys are stamped with death time and purged after 30d", async () => {
  const envelope = makeEnvelope({ id: uid(2), createdMs: Date.now() - 1000 });
  await globalThis.EDGE_CONFIG.put(pendingKeyOf(envelope), JSON.stringify(envelope));
  stubFetch(422);
  await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 5 });
  const deadKeys = (await globalThis.EDGE_CONFIG.list({ prefix: "d_", limit: 10 })).keys.map((k) => k.key);
  assert.equal(deadKeys.length, 1);
  const stamp = Number(deadKeys[0].slice(2, 18));
  assert.ok(Math.abs(stamp - Date.now()) < 60_000);

  const realNow = Date.now;
  try {
    const later = realNow() + 31 * 24 * 3600_000;
    Date.now = () => later;
    stubFetch(200);
    await drainPending({ UPSTREAM_URL: "https://up.example" }, { eligible: 5 });
    assert.equal((await globalThis.EDGE_CONFIG.list({ prefix: "d_", limit: 10 })).keys.length, 0);
  } finally {
    Date.now = realNow;
  }
});

test("admin status paginates counts past one page", async () => {
  const base = Date.now();
  for (let i = 0; i < 300; i++) {
    const envelope = makeEnvelope({
      id: uid(i),
      createdMs: base - 300 + i,
      nextAttemptMs: base + 3600_000,
    });
    await globalThis.EDGE_CONFIG.put(pendingKeyOf(envelope), JSON.stringify(envelope));
  }
  await writeConfig();
  const res = await onRequest(context(new Request("https://edge/admin/status", {
    headers: { Authorization: "Bearer admin" },
  })).ctx);
  const body = await res.json();
  assert.equal(body.pending, 300);
  assert.equal(body.truncated, false);
  assert.ok(body.oldest_pending_at);
});
