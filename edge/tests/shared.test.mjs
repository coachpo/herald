import assert from "node:assert/strict";
import test from "node:test";

import { authenticateIngest, sha256Hex } from "../shared/auth.mjs";
import { makeConfigLoader } from "../shared/config-cache.mjs";
import {
  backoffSeconds,
  buildEnvelope,
  forwardEnvelope,
  parseRelayHeaders,
} from "../shared/relay.mjs";
import { validatePayload } from "../shared/validate.mjs";

test("sha256Hex known vector", async () => {
  assert.equal(
    await sha256Hex("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
});

test("authenticateIngest matches endpoint digest", async () => {
  const key = "secret";
  const ep = { id: "550e8400-e29b-41d4-a716-446655440000", key_sha256: await sha256Hex(key) };
  const config = { ingest_endpoints: [ep] };

  assert.equal(await authenticateIngest(config, ep.id.replaceAll("-", ""), key), ep);
  assert.equal(await authenticateIngest(config, ep.id, "wrong"), null);
  assert.equal(await authenticateIngest(config, crypto.randomUUID(), key), null);
});

test("validatePayload rejects unknown and missing body", () => {
  assert.equal(validatePayload({ body: "ok" }).ok, true);
  assert.deepEqual(validatePayload({ body: "ok", nope: 1 }), {
    ok: false,
    error: "unknown_field:nope",
  });
  assert.deepEqual(validatePayload({ title: "x" }), { ok: false, error: "missing_body" });
});

test("parseRelayHeaders validates id and cleans via", () => {
  const id = "550e8400-e29b-41d4-a716-446655440000";
  const req = new Request("https://x", {
    headers: {
      "X-Herald-Message-Id": id,
      "X-Herald-Received-At": "2026-01-01T00:00:00Z",
      "X-Herald-Relay-Via": "EdgeOne!!,Cloudflare",
    },
  });
  assert.deepEqual(parseRelayHeaders(req), {
    id,
    receivedAt: "2026-01-01T00:00:00Z",
    via: "edgeone,cloudflare",
  });
  assert.equal(parseRelayHeaders(new Request("https://x", { headers: { "X-Herald-Message-Id": "bad" } })).id, null);
});

test("buildEnvelope fills relay envelope", () => {
  const e = buildEnvelope({
    endpointId: "ep",
    rawKey: "k",
    body: "{}",
    via: "cloudflare",
    nowIso: "now",
  });
  assert.equal(e.endpoint_id, "ep");
  assert.equal(e.received_at, "now");
  assert.equal(e.attempts, 0);
});

test("forwardEnvelope sends headers and classifies responses", async () => {
  const envelope = {
    id: "id",
    endpoint_id: "ep",
    received_at: "now",
    via: "cloudflare",
    ingest_key: "key",
    body: "{}",
  };
  let seen;
  const ok = await forwardEnvelope(envelope, "https://up/", async (url, init) => {
    seen = { url, init };
    return new Response("ok", { status: 201 });
  });
  assert.deepEqual(ok, { ok: true });
  assert.equal(seen.url, "https://up/api/ingest/ep");
  assert.equal(seen.init.headers["X-Herald-Ingest-Key"], "key");

  assert.deepEqual(
    await forwardEnvelope(envelope, "https://up", async () => new Response("bad", { status: 422 })),
    { ok: false, permanent: true, error: "upstream_status_422" },
  );
  assert.deepEqual(
    await forwardEnvelope(envelope, "https://up", async () => new Response("bad", { status: 500 })),
    { ok: false, permanent: false, error: "upstream_status_500" },
  );
});

test("backoffSeconds caps", () => {
  assert.deepEqual([1, 2, 3, 20].map(backoffSeconds), [5, 10, 20, 3600]);
});

test("makeConfigLoader caches with ttl", async () => {
  let calls = 0;
  const load = makeConfigLoader(async () => ({ version: String(++calls) }), 100);
  assert.equal((await load(0)).version, "1");
  assert.equal((await load(50)).version, "1");
  assert.equal((await load(101)).version, "2");
});
