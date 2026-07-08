import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../shared/auth.mjs";
import { handleRequest, RelayBuffer } from "../cloudflare/src/worker.mjs";

class FakeSql {
  constructor() {
    this.pending = new Map();
    this.dead = new Map();
  }

  exec(query, ...args) {
    if (query.startsWith("CREATE TABLE")) return result();
    if (query.startsWith("INSERT OR IGNORE INTO pending")) {
      const [id, endpointId, receivedAt, via, ingestKey, body, nextAttemptMs, createdMs] = args;
      if (!this.pending.has(id)) {
        this.pending.set(id, {
          id,
          endpoint_id: endpointId,
          received_at: receivedAt,
          via,
          ingest_key: ingestKey,
          body,
          attempts: 0,
          next_attempt_ms: nextAttemptMs,
          last_error: null,
          created_ms: createdMs,
        });
      }
      return result();
    }
    if (query.startsWith("SELECT * FROM pending WHERE id = ?")) {
      const row = this.pending.get(args[0]);
      return result(row ? [row] : []);
    }
    if (query.startsWith("DELETE FROM pending WHERE id = ?")) {
      this.pending.delete(args[0]);
      return result();
    }
    if (query.startsWith("UPDATE pending SET attempts = ?")) {
      const row = this.pending.get(args[3]);
      if (row) {
        row.attempts = args[0];
        row.next_attempt_ms = args[1];
        row.last_error = args[2];
      }
      return result();
    }
    if (query.startsWith("SELECT id FROM pending WHERE next_attempt_ms <= ?")) {
      const rows = [...this.pending.values()]
        .filter((row) => row.next_attempt_ms <= args[0])
        .sort((a, b) => a.created_ms - b.created_ms)
        .slice(0, 25)
        .map(({ id }) => ({ id }));
      return result(rows);
    }
    if (query.startsWith("SELECT id FROM pending ORDER BY created_ms")) {
      return result([...this.pending.values()]
        .sort((a, b) => a.created_ms - b.created_ms)
        .slice(0, 25)
        .map(({ id }) => ({ id })));
    }
    if (query.startsWith("DELETE FROM dead WHERE died_ms < ?")) {
      for (const [id, row] of this.dead) {
        if (row.died_ms < args[0]) this.dead.delete(id);
      }
      return result();
    }
    if (query.startsWith("SELECT COUNT(*) AS n, MIN(created_ms) AS oldest FROM pending")) {
      const rows = [...this.pending.values()];
      return result([{ n: rows.length, oldest: rows.length ? Math.min(...rows.map((row) => row.created_ms)) : null }]);
    }
    if (query.startsWith("SELECT COUNT(*) AS n FROM dead")) {
      return result([{ n: this.dead.size }]);
    }
    if (query.startsWith("SELECT MIN(next_attempt_ms) AS ts FROM pending")) {
      const rows = [...this.pending.values()];
      return result([{ ts: rows.length ? Math.min(...rows.map((row) => row.next_attempt_ms)) : null }]);
    }
    if (query.startsWith("INSERT OR REPLACE INTO dead")) {
      this.dead.set(args[0], { id: args[0], envelope: args[1], reason: args[2], died_ms: args[3] });
      return result();
    }
    throw new Error(`unhandled query: ${query}`);
  }
}

function result(rows = []) {
  return {
    toArray: () => rows,
    one: () => rows[0] ?? {},
  };
}

function relayBuffer(fetchImpl) {
  const sql = new FakeSql();
  const alarms = [];
  const ctx = {
    storage: {
      sql,
      setAlarm: async (ts) => alarms.push(ts),
    },
  };
  const previousFetch = globalThis.fetch;
  globalThis.fetch = fetchImpl;
  return {
    buffer: new RelayBuffer(ctx, { UPSTREAM_URL: "https://backend.example.com" }),
    sql,
    alarms,
    restore: () => {
      globalThis.fetch = previousFetch;
    },
  };
}

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

test("RelayBuffer retries temporary failures and reports status", async () => {
  const { buffer, sql, alarms, restore } = relayBuffer(async () => new Response("bad", { status: 500 }));
  try {
    const res = await buffer.fetch(new Request("https://do/enqueue", {
      method: "POST",
      body: JSON.stringify({
        id: "msg-1",
        endpoint_id: "ep",
        received_at: "2026-01-01T00:00:00Z",
        via: "cloudflare",
        ingest_key: "raw-key",
        body: "{}",
      }),
    }));
    assert.equal(res.status, 200);
    assert.equal(sql.pending.size, 1);
    const row = sql.pending.get("msg-1");
    assert.equal(row.attempts, 1);
    assert.equal(row.last_error, "upstream_status_500");
    assert.equal(alarms.length, 1);

    const status = await (await buffer.fetch(new Request("https://do/status"))).json();
    assert.equal(status.pending, 1);
    assert.equal(status.dead, 0);
    assert.equal(status.oldest_pending_at, new Date(row.created_ms).toISOString());
  } finally {
    restore();
  }
});

test("RelayBuffer drains successes and moves permanent failures to dead", async () => {
  const ok = relayBuffer(async () => new Response("ok", { status: 201 }));
  try {
    await ok.buffer.fetch(new Request("https://do/enqueue", {
      method: "POST",
      body: JSON.stringify({
        id: "msg-ok",
        endpoint_id: "ep",
        received_at: "2026-01-01T00:00:00Z",
        via: "cloudflare",
        ingest_key: "raw-key",
        body: "{}",
      }),
    }));
    assert.equal(ok.sql.pending.size, 0);
    assert.deepEqual(await (await ok.buffer.fetch(new Request("https://do/drain", { method: "POST" }))).json(), {
      drained: 0,
      failed: 0,
      dead: 0,
    });
  } finally {
    ok.restore();
  }

  const dead = relayBuffer(async () => new Response("bad", { status: 422 }));
  try {
    await dead.buffer.fetch(new Request("https://do/enqueue", {
      method: "POST",
      body: JSON.stringify({
        id: "msg-dead",
        endpoint_id: "ep",
        received_at: "2026-01-01T00:00:00Z",
        via: "cloudflare",
        ingest_key: "raw-key",
        body: "{}",
      }),
    }));
    assert.equal(dead.sql.pending.size, 0);
    assert.equal(dead.sql.dead.size, 1);
    const stored = JSON.parse(dead.sql.dead.get("msg-dead").envelope);
    assert.equal(stored.ingest_key, "[redacted]");
  } finally {
    dead.restore();
  }
});
