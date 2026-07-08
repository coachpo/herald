import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../shared/auth.mjs";
import { onRequest } from "../edgeone/edge-functions/[[default]].js";

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
  async list({ prefix = "", limit = 256 } = {}) {
    return {
      keys: [...this.map.keys()]
        .filter((key) => key.startsWith(prefix))
        .sort()
        .slice(0, limit)
        .map((key) => ({ key })),
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

async function writeConfig(key = "raw-key") {
  const endpoint = {
    id: "550e8400-e29b-41d4-a716-446655440000",
    key_sha256: await sha256Hex(key),
  };
  const { ctx } = context(new Request("https://edge/admin/config", {
    method: "POST",
    headers: { Authorization: "Bearer admin" },
    body: JSON.stringify({ version: "v1", ingest_endpoints: [endpoint] }),
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
