import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../shared/auth.mjs";
import { handleRequest } from "../cloudflare/src/worker.mjs";

async function envWithConfig(config) {
  const calls = [];
  const stub = {
    fetch: async (url, init) => {
      calls.push({ url, init });
      if (String(url).endsWith("/status")) return Response.json({ pending: 0, dead: 0 });
      return Response.json({ ok: true });
    },
  };
  return {
    calls,
    env: {
      RELAY_ADMIN_TOKEN: "admin",
      UPSTREAM_URL: "https://backend.example.com",
      EDGE_CONFIG: {
        get: async () => config,
        put: async () => {},
      },
      RELAY_BUFFER: {
        idFromName: (name) => name,
        get: () => stub,
      },
    },
  };
}

test("healthz", async () => {
  const { env } = await envWithConfig(null);
  const res = await handleRequest(new Request("https://edge/healthz"), env);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, mode: "relay", platform: "cloudflare" });
});

test("admin auth and config validation", async () => {
  const { env } = await envWithConfig(null);
  assert.equal((await handleRequest(new Request("https://edge/admin/status"), env)).status, 403);
  assert.equal(
    (await handleRequest(new Request("https://edge/admin/status", {
      headers: { Authorization: "Bearer wrong" },
    }), env)).status,
    403,
  );
  assert.equal(
    (await handleRequest(new Request("https://edge/admin/config", {
      method: "POST",
      headers: { Authorization: "Bearer admin" },
      body: "not json",
    }), env)).status,
    400,
  );
});

test("ingest authenticates and enqueues envelope", async () => {
  const key = "raw-key";
  const endpoint = {
    id: "550e8400-e29b-41d4-a716-446655440000",
    key_sha256: await sha256Hex(key),
  };
  const { env, calls } = await envWithConfig({
    version: "v1",
    ingest_endpoints: [endpoint],
  });
  const res = await handleRequest(new Request(`https://edge/api/ingest/${endpoint.id.replaceAll("-", "")}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Herald-Ingest-Key": key,
      "X-Herald-Message-Id": "11111111-1111-4111-8111-111111111111",
      "X-Herald-Relay-Via": "edgeone",
    },
    body: JSON.stringify({ body: "hello" }),
  }), env);

  assert.equal(res.status, 202);
  const body = await res.json();
  assert.equal(body.message_id, "11111111-1111-4111-8111-111111111111");
  assert.equal(calls.length, 1);
  const envelope = JSON.parse(calls[0].init.body);
  assert.equal(envelope.via, "edgeone,cloudflare");
  assert.equal(envelope.ingest_key, key);
});

test("ingest rejects bad auth and validation", async () => {
  const key = "raw-key";
  const endpoint = {
    id: "550e8400-e29b-41d4-a716-446655440000",
    key_sha256: await sha256Hex(key),
  };
  const { env } = await envWithConfig({ ingest_endpoints: [endpoint] });
  assert.equal(
    (await handleRequest(new Request(`https://edge/api/ingest/${endpoint.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Herald-Ingest-Key": "bad" },
      body: JSON.stringify({ body: "hello" }),
    }), env)).status,
    401,
  );
  assert.equal(
    (await handleRequest(new Request(`https://edge/api/ingest/${endpoint.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Herald-Ingest-Key": key },
      body: JSON.stringify({ body: "hello", nope: true }),
    }), env)).status,
    422,
  );
});
