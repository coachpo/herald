import test from "node:test";
import assert from "node:assert/strict";

import { ruleMatchesMessage } from "./rules.mjs";
import { renderTemplate, buildTemplateContext } from "./template.mjs";
import {
  buildBarkPushUrl,
  buildBarkPayload,
  buildNtfyRequest,
} from "./providers.mjs";
import { handleLiteRequest } from "./lite.mjs";

// ---------------------------------------------------------------------------
// rules.mjs
// ---------------------------------------------------------------------------

test("rules: empty filter matches everything", () => {
  assert.ok(ruleMatchesMessage({}, { body: "hello" }));
  assert.ok(ruleMatchesMessage(null, { body: "hello" }));
});

test("rules: ingest_endpoint_ids filter", () => {
  const f = { ingest_endpoint_ids: ["ep-1", "ep-2"] };
  assert.ok(ruleMatchesMessage(f, { ingest_endpoint_id: "ep-1", body: "x" }));
  assert.ok(!ruleMatchesMessage(f, { ingest_endpoint_id: "ep-3", body: "x" }));
});

test("rules: body.contains filter (case-insensitive, any match)", () => {
  const f = { body: { contains: ["ERROR", "warn"] } };
  assert.ok(ruleMatchesMessage(f, { body: "an error occurred" }));
  assert.ok(ruleMatchesMessage(f, { body: "WARNING: disk full" }));
  assert.ok(!ruleMatchesMessage(f, { body: "all good" }));
});

test("rules: body.regex filter", () => {
  const f = { body: { regex: "^ERR-\\d+" } };
  assert.ok(ruleMatchesMessage(f, { body: "ERR-123 something" }));
  assert.ok(!ruleMatchesMessage(f, { body: "no match" }));
});

test("rules: invalid regex rejects", () => {
  const f = { body: { regex: "[invalid" } };
  assert.ok(!ruleMatchesMessage(f, { body: "anything" }));
});

test("rules: priority min/max filter", () => {
  const f = { priority: { min: 3, max: 4 } };
  assert.ok(ruleMatchesMessage(f, { body: "x", priority: 3 }));
  assert.ok(ruleMatchesMessage(f, { body: "x", priority: 4 }));
  assert.ok(!ruleMatchesMessage(f, { body: "x", priority: 2 }));
  assert.ok(!ruleMatchesMessage(f, { body: "x", priority: 5 }));
});

test("rules: priority defaults to 3 when missing", () => {
  assert.ok(ruleMatchesMessage({ priority: { min: 3 } }, { body: "x" }));
  assert.ok(!ruleMatchesMessage({ priority: { min: 4 } }, { body: "x" }));
});

test("rules: tags filter (any match, case-insensitive)", () => {
  const f = { tags: ["urgent", "critical"] };
  assert.ok(ruleMatchesMessage(f, { body: "x", tags: ["URGENT", "info"] }));
  assert.ok(!ruleMatchesMessage(f, { body: "x", tags: ["info"] }));
  assert.ok(!ruleMatchesMessage(f, { body: "x", tags: [] }));
});

test("rules: group filter (exact match)", () => {
  const f = { group: "deploy" };
  assert.ok(ruleMatchesMessage(f, { body: "x", group: "deploy" }));
  assert.ok(!ruleMatchesMessage(f, { body: "x", group: "other" }));
  assert.ok(!ruleMatchesMessage(f, { body: "x" }));
});

test("rules: combined filters (all must match)", () => {
  const f = {
    ingest_endpoint_ids: ["ep-1"],
    body: { contains: ["alert"] },
    priority: { min: 4 },
    tags: ["ops"],
  };
  assert.ok(
    ruleMatchesMessage(f, {
      ingest_endpoint_id: "ep-1",
      body: "alert: disk full",
      priority: 4,
      tags: ["ops"],
    }),
  );
  assert.ok(
    !ruleMatchesMessage(f, {
      ingest_endpoint_id: "ep-1",
      body: "alert: disk full",
      priority: 2,
      tags: ["ops"],
    }),
  );
});

// ---------------------------------------------------------------------------
// template.mjs
// ---------------------------------------------------------------------------

test("template: renders string variables", () => {
  const ctx = { message: { body: "hello", title: "Hi" } };
  assert.equal(renderTemplate("Body: {{message.body}}", ctx), "Body: hello");
});

test("template: missing variable renders empty", () => {
  assert.equal(renderTemplate("{{missing.path}}", {}), "");
});

test("template: renders nested objects", () => {
  const ctx = { message: { body: "b", title: "t" } };
  const result = renderTemplate(
    { body: "{{message.body}}", title: "{{message.title}}" },
    ctx,
  );
  assert.deepEqual(result, { body: "b", title: "t" });
});

test("template: renders arrays", () => {
  const ctx = { message: { body: "b" } };
  const result = renderTemplate(["{{message.body}}", "static"], ctx);
  assert.deepEqual(result, ["b", "static"]);
});

test("template: non-string values pass through", () => {
  assert.equal(renderTemplate(42, {}), 42);
  assert.equal(renderTemplate(null, {}), null);
  assert.equal(renderTemplate(true, {}), true);
});

test("template: buildTemplateContext shapes correctly", () => {
  const msg = {
    id: "msg-1",
    received_at: "2026-01-01T00:00:00Z",
    body: "hello",
    title: "Hi",
    group: "g",
    priority: 4,
    tags: ["a", "b"],
    url: "https://example.com",
    extras: { k: "v" },
    content_type: "application/json",
    remote_ip: "1.2.3.4",
    user_agent: "curl",
    headers: { "X-Custom": "val" },
    query: { q: "1" },
  };
  const ep = { id: "ep-1", name: "My EP" };
  const ctx = buildTemplateContext(msg, ep);

  assert.equal(ctx.message.id, "msg-1");
  assert.equal(ctx.message.body, "hello");
  assert.equal(ctx.message.priority, "4");
  assert.equal(ctx.message.tags, "a,b");
  assert.equal(ctx.request.remote_ip, "1.2.3.4");
  assert.equal(ctx.ingest_endpoint.name, "My EP");
});

// ---------------------------------------------------------------------------
// providers.mjs
// ---------------------------------------------------------------------------

test("providers: buildBarkPushUrl normalizes", () => {
  assert.equal(buildBarkPushUrl("https://bark.example.com"), "https://bark.example.com/push");
  assert.equal(buildBarkPushUrl("https://bark.example.com/"), "https://bark.example.com/push");
  assert.equal(buildBarkPushUrl("https://bark.example.com/push"), "https://bark.example.com/push");
});

test("providers: buildBarkPayload merges defaults and rendered", () => {
  const payload = buildBarkPayload({
    channelConfig: {
      device_key: "dk",
      default_payload_json: { sound: "bell" },
    },
    payloadTemplate: {},
    rendered: { body: "rendered body", title: "rendered title" },
    message: { body: "msg body", title: "msg title" },
  });
  assert.equal(payload.body, "rendered body");
  assert.equal(payload.title, "rendered title");
  assert.equal(payload.sound, "bell");
  assert.equal(payload.device_key, "dk");
});

test("providers: buildBarkPayload falls back to message body/title", () => {
  const payload = buildBarkPayload({
    channelConfig: { device_key: "dk" },
    payloadTemplate: {},
    rendered: {},
    message: { body: "msg body", title: "msg title" },
  });
  assert.equal(payload.body, "msg body");
  assert.equal(payload.title, "msg title");
});

test("providers: buildNtfyRequest builds correct url and body", () => {
  const req = buildNtfyRequest({
    channelConfig: {
      server_base_url: "https://ntfy.sh",
      topic: "test-topic",
    },
    rendered: { body: "hello" },
    message: { body: "fallback", priority: 3 },
  });
  assert.equal(req.url, "https://ntfy.sh/test-topic");
  assert.equal(req.body, "hello");
});

test("providers: buildNtfyRequest throws on missing server_base_url", () => {
  assert.throws(
    () =>
      buildNtfyRequest({
        channelConfig: { topic: "t" },
        rendered: {},
        message: { body: "x" },
      }),
    /missing_server_base_url/,
  );
});

test("providers: buildNtfyRequest throws on missing topic", () => {
  assert.throws(
    () =>
      buildNtfyRequest({
        channelConfig: { server_base_url: "https://ntfy.sh" },
        rendered: {},
        message: { body: "x" },
      }),
    /missing_topic/,
  );
});

test("providers: buildNtfyRequest sets auth header from access_token", () => {
  const req = buildNtfyRequest({
    channelConfig: {
      server_base_url: "https://ntfy.sh",
      topic: "t",
      access_token: "tok123",
    },
    rendered: { body: "hi" },
    message: { body: "x" },
  });
  assert.equal(req.headers.Authorization, "Bearer tok123");
});

test("providers: buildNtfyRequest maps priority to ntfy names", () => {
  const req = buildNtfyRequest({
    channelConfig: { server_base_url: "https://ntfy.sh", topic: "t" },
    rendered: {},
    message: { body: "x", priority: 5 },
  });
  assert.equal(req.headers.Priority, "urgent");
});

test("providers: buildNtfyRequest sets title from rendered", () => {
  const req = buildNtfyRequest({
    channelConfig: { server_base_url: "https://ntfy.sh", topic: "t" },
    rendered: { title: "My Title", body: "b" },
    message: { body: "x" },
  });
  assert.equal(req.headers.Title, "My Title");
});

test("providers: buildNtfyRequest applies default_headers_json", () => {
  const req = buildNtfyRequest({
    channelConfig: {
      server_base_url: "https://ntfy.sh",
      topic: "t",
      default_headers_json: { Icon: "https://example.com/icon.png" },
    },
    rendered: { body: "b" },
    message: { body: "x" },
  });
  assert.equal(req.headers.Icon, "https://example.com/icon.png");
});

// ---------------------------------------------------------------------------
// lite.mjs — integration tests
// ---------------------------------------------------------------------------

function makeConfig() {
  return {
    ingest_endpoints: [
      { id: "aaaa-bbbb-cccc-dddd", name: "ep1", token_hash: "secret-hash" },
    ],
    channels: [
      {
        id: "ch-bark-1",
        type: "bark",
        name: "Bark",
        config: {
          server_base_url: "https://bark.example.com",
          device_key: "dk",
        },
      },
      {
        id: "ch-ntfy-1",
        type: "ntfy",
        name: "Ntfy",
        config: {
          server_base_url: "https://ntfy.sh",
          topic: "test",
        },
      },
    ],
    rules: [
      {
        id: "rule-1",
        name: "Bark all",
        filter: {},
        channel_id: "ch-bark-1",
        payload_template: { body: "{{message.body}}" },
      },
      {
        id: "rule-2",
        name: "Ntfy urgent",
        filter: { priority: { min: 4 } },
        channel_id: "ch-ntfy-1",
        payload_template: { body: "{{message.body}}", title: "Alert" },
      },
    ],
    version: "abc123",
  };
}

function makeKV(config) {
  return {
    get(_key, _type) {
      return Promise.resolve(config);
    },
  };
}

function makeEnv(config) {
  return { EDGE_CONFIG: makeKV(config) };
}

function makeRequest(endpointId, body, headers = {}) {
  return new Request(
    `https://edge.example/api/ingest/${endpointId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Herald-Ingest-Key": "secret-hash",
        ...headers,
      },
      body: JSON.stringify(body),
    },
  );
}

test("lite: healthz returns ok with mode lite", async () => {
  const req = new Request("https://edge.example/healthz");
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.mode, "lite");
});

test("lite: 404 for unknown path", async () => {
  const req = new Request("https://edge.example/unknown", { method: "POST" });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 404);
});

test("lite: 405 for GET on ingest path", async () => {
  const req = new Request("https://edge.example/api/ingest/abcd", {
    method: "GET",
  });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 405);
});

test("lite: 415 for non-json content type", async () => {
  const req = new Request("https://edge.example/api/ingest/abcd", {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: "hello",
  });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 415);
});

test("lite: 401 for unknown endpoint id", async () => {
  const req = makeRequest("00000000000000000000000000000000", { body: "hi" });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 401);
});

test("lite: 401 for wrong ingest key", async () => {
  const req = new Request(
    "https://edge.example/api/ingest/aaaabbbbccccdddd",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Herald-Ingest-Key": "wrong-key",
      },
      body: JSON.stringify({ body: "hi" }),
    },
  );
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 401);
});

test("lite: 422 for unknown field in payload", async () => {
  const req = makeRequest("aaaabbbbccccdddd", { body: "hi", unknown_field: 1 });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 422);
});

test("lite: 422 for missing body field", async () => {
  const req = makeRequest("aaaabbbbccccdddd", { title: "no body" });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 422);
});

test("lite: 500 when config not loaded", async () => {
  const req = makeRequest("aaaabbbbccccdddd", { body: "hi" });
  const resp = await handleLiteRequest(req, { EDGE_CONFIG: { get: () => Promise.resolve(null) } });
  assert.equal(resp.status, 500);
});

test("lite: successful dispatch returns 201 with results", async () => {
  const fetchCalls = [];
  globalThis.fetch = async (url, opts) => {
    fetchCalls.push({ url: typeof url === "string" ? url : url.toString(), method: opts?.method });
    return new Response("{}", { status: 200 });
  };

  const req = makeRequest("aaaabbbbccccdddd", { body: "hello", priority: 4 });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 201);

  const data = await resp.json();
  assert.ok(data.message_id);
  assert.equal(data.matched_rules, 2);
  assert.equal(data.dispatched, 2);
  assert.equal(data.results.length, 2);

  const barkResult = data.results.find((r) => r.type === "bark");
  assert.ok(barkResult);
  assert.ok(barkResult.ok);

  const ntfyResult = data.results.find((r) => r.type === "ntfy");
  assert.ok(ntfyResult);
  assert.ok(ntfyResult.ok);

  assert.ok(fetchCalls.some((c) => c.url.includes("bark.example.com/push")));
  assert.ok(fetchCalls.some((c) => c.url.includes("ntfy.sh/test")));
});

test("lite: low priority message only matches catch-all rule", async () => {
  globalThis.fetch = async () => new Response("{}", { status: 200 });

  const req = makeRequest("aaaabbbbccccdddd", { body: "hello", priority: 2 });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 201);

  const data = await resp.json();
  assert.equal(data.matched_rules, 1);
  assert.equal(data.results.length, 1);
  assert.equal(data.results[0].type, "bark");
});

test("lite: dispatch failure is captured in results", async () => {
  globalThis.fetch = async () => new Response("error", { status: 500 });

  const req = makeRequest("aaaabbbbccccdddd", { body: "hello" });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 201);

  const data = await resp.json();
  assert.ok(data.results.length > 0);
  assert.ok(data.results.some((r) => !r.ok));
});

test("lite: fetch exception is captured in results", async () => {
  globalThis.fetch = async () => {
    throw new Error("network down");
  };

  const req = makeRequest("aaaabbbbccccdddd", { body: "hello" });
  const resp = await handleLiteRequest(req, makeEnv(makeConfig()));
  assert.equal(resp.status, 201);

  const data = await resp.json();
  assert.ok(data.results.length > 0);
  assert.ok(data.results.some((r) => !r.ok && r.error));
});
