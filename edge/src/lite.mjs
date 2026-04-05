import { ruleMatchesMessage } from "./rules.mjs";
import { buildTemplateContext, renderTemplate } from "./template.mjs";
import {
  buildBarkPayload,
  sendBarkPush,
  buildNtfyRequest,
  sendNtfyPublish,
} from "./providers.mjs";

function jsonResponse(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function parseIngestEndpointIdFromPath(pathname) {
  const parts = String(pathname || "")
    .split("/")
    .filter(Boolean);
  if (parts.length !== 3) return "";
  if (parts[0] !== "api" || parts[1] !== "ingest") return "";
  return parts[2];
}

function constantTimeEqual(a, b) {
  const aa = String(a || "");
  const bb = String(b || "");
  if (aa.length !== bb.length) return false;
  let out = 0;
  for (let i = 0; i < aa.length; i++) {
    out |= aa.charCodeAt(i) ^ bb.charCodeAt(i);
  }
  return out === 0;
}

function validatePayload(json) {
  if (typeof json !== "object" || json === null || Array.isArray(json)) {
    return { ok: false, error: "invalid_json_object" };
  }

  const allowed = new Set([
    "body",
    "title",
    "group",
    "priority",
    "tags",
    "url",
    "extras",
  ]);
  for (const key of Object.keys(json)) {
    if (!allowed.has(key)) {
      return { ok: false, error: `unknown_field:${key}` };
    }
  }

  if (typeof json.body !== "string" || !json.body.trim()) {
    return { ok: false, error: "missing_body" };
  }

  if (json.title != null && typeof json.title !== "string") {
    return { ok: false, error: "invalid_title" };
  }
  if (json.group != null && typeof json.group !== "string") {
    return { ok: false, error: "invalid_group" };
  }
  if (json.priority != null) {
    const p = Number(json.priority);
    if (!Number.isInteger(p) || p < 1 || p > 5) {
      return { ok: false, error: "invalid_priority" };
    }
  }
  if (json.tags != null) {
    if (!Array.isArray(json.tags)) {
      return { ok: false, error: "invalid_tags" };
    }
  }
  if (json.url != null && typeof json.url !== "string") {
    return { ok: false, error: "invalid_url" };
  }
  if (json.extras != null) {
    if (typeof json.extras !== "object" || Array.isArray(json.extras)) {
      return { ok: false, error: "invalid_extras" };
    }
  }

  return { ok: true };
}

export async function handleLiteRequest(request, env) {
  const url = new URL(request.url);

  if (url.pathname === "/healthz") {
    return jsonResponse({ ok: true, mode: "lite" }, 200);
  }

  const endpointId = parseIngestEndpointIdFromPath(url.pathname);
  if (!endpointId) {
    return jsonResponse({ code: "not_found", message: "not found" }, 404);
  }

  if (request.method !== "POST") {
    return jsonResponse(
      { code: "method_not_allowed", message: "method not allowed" },
      405,
    );
  }

  const contentType = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonResponse(
      { code: "unsupported_media_type", message: "Content-Type must be application/json" },
      415,
    );
  }

  const config = await loadConfig(env);
  if (!config) {
    return jsonResponse(
      { code: "misconfigured", message: "edge config not loaded" },
      500,
    );
  }

  const endpoint = config.ingest_endpoints.find(
    (ep) => ep.id.replace(/-/g, "") === endpointId.replace(/-/g, ""),
  );
  if (!endpoint) {
    return jsonResponse(
      { code: "not_authenticated", message: "unauthorized" },
      401,
    );
  }

  const ingestKey = request.headers.get("X-Herald-Ingest-Key") || "";
  if (!constantTimeEqual(ingestKey.trim(), endpoint.token_hash)) {
    return jsonResponse(
      { code: "not_authenticated", message: "unauthorized" },
      401,
    );
  }

  let body;
  try {
    body = await request.text();
  } catch {
    return jsonResponse(
      { code: "bad_request", message: "failed to read body" },
      400,
    );
  }

  const maxBytes = 1024 * 1024;
  if (new TextEncoder().encode(body).length > maxBytes) {
    return jsonResponse(
      { code: "payload_too_large", message: "max 1MB" },
      413,
    );
  }

  let json;
  try {
    json = JSON.parse(body);
  } catch {
    return jsonResponse(
      { code: "bad_request", message: "invalid JSON" },
      400,
    );
  }

  const validation = validatePayload(json);
  if (!validation.ok) {
    return jsonResponse(
      { code: "validation_error", message: validation.error },
      422,
    );
  }

  const message = {
    id: crypto.randomUUID(),
    received_at: new Date().toISOString(),
    body: json.body,
    title: json.title || null,
    group: json.group || null,
    priority: json.priority != null ? Number(json.priority) : 3,
    tags: json.tags || [],
    url: json.url || null,
    extras: json.extras || {},
    ingest_endpoint_id: endpoint.id,
    content_type: contentType,
    remote_ip: request.headers.get("CF-Connecting-IP") || "",
    user_agent: request.headers.get("User-Agent") || "",
    headers: {},
    query: Object.fromEntries(url.searchParams.entries()),
  };

  const channelMap = {};
  for (const ch of config.channels) {
    channelMap[ch.id] = ch;
  }

  const matchedRules = config.rules.filter((rule) =>
    ruleMatchesMessage(rule.filter, message),
  );

  const results = [];
  const dispatches = [];

  for (const rule of matchedRules) {
    const channel = channelMap[rule.channel_id];
    if (!channel) continue;

    const ctx = buildTemplateContext(message, endpoint);
    const rendered = renderTemplate(rule.payload_template || {}, ctx);

    if (channel.type === "bark") {
      const serverBaseUrl = (channel.config.server_base_url || "").trim();
      if (!serverBaseUrl) continue;

      const payload = buildBarkPayload({
        channelConfig: channel.config,
        payloadTemplate: rule.payload_template,
        rendered,
        message,
      });

      dispatches.push(
        sendBarkPush({ serverBaseUrl, payload })
          .then((r) => results.push({ rule: rule.id, channel: channel.id, type: "bark", ...r }))
          .catch((e) => results.push({ rule: rule.id, channel: channel.id, type: "bark", ok: false, error: String(e) })),
      );
    } else if (channel.type === "ntfy") {
      try {
        const req = buildNtfyRequest({
          channelConfig: channel.config,
          rendered,
          message,
        });
        dispatches.push(
          sendNtfyPublish(req)
            .then((r) => results.push({ rule: rule.id, channel: channel.id, type: "ntfy", ...r }))
            .catch((e) => results.push({ rule: rule.id, channel: channel.id, type: "ntfy", ok: false, error: String(e) })),
        );
      } catch (e) {
        results.push({
          rule: rule.id,
          channel: channel.id,
          type: "ntfy",
          ok: false,
          error: String(e),
        });
      }
    }
  }

  await Promise.allSettled(dispatches);

  return jsonResponse(
    {
      message_id: message.id,
      matched_rules: matchedRules.length,
      dispatched: results.length,
      results,
    },
    201,
  );
}

async function loadConfig(env) {
  if (env._liteConfig) return env._liteConfig;

  const kv = env.EDGE_CONFIG;
  if (!kv) return null;

  try {
    const raw = await kv.get("config", "json");
    if (raw) {
      env._liteConfig = raw;
      return raw;
    }
  } catch {
    return null;
  }

  return null;
}
