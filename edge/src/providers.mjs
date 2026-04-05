export function buildBarkPushUrl(serverBaseUrl) {
  let base = (serverBaseUrl || "").trim().replace(/\/+$/, "");
  if (base.endsWith("/push")) {
    base = base.slice(0, -"/push".length);
  }
  return base.replace(/\/+$/, "") + "/push";
}

export function buildBarkPayload({ channelConfig, payloadTemplate, rendered, message }) {
  const defaultPayload = channelConfig.default_payload_json || {};
  const payload = { ...defaultPayload };

  if (rendered && typeof rendered === "object" && !Array.isArray(rendered)) {
    Object.assign(payload, rendered);
  }

  if (!payload.body && message.body) payload.body = message.body;
  if (!payload.title && message.title) payload.title = message.title;

  if (channelConfig.device_key != null) payload.device_key = channelConfig.device_key;
  if (channelConfig.device_keys != null) payload.device_keys = channelConfig.device_keys;

  return payload;
}

export async function sendBarkPush({ serverBaseUrl, payload }) {
  const url = buildBarkPushUrl(serverBaseUrl);
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return { ok: resp.status >= 200 && resp.status < 300, status: resp.status };
}

function coerceHeaderValue(v) {
  if (v == null) return null;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") {
    const s = v.trim();
    return s || null;
  }
  return String(v);
}

const PRIORITY_MAP = { 1: "min", 2: "low", 3: "default", 4: "high", 5: "urgent" };

export function buildNtfyRequest({ channelConfig, rendered, message }) {
  const serverBaseUrl = (channelConfig.server_base_url || "").trim();
  const topic = (channelConfig.topic || "").trim();
  if (!serverBaseUrl) throw new Error("missing_server_base_url");
  if (!topic) throw new Error("missing_topic");

  const url = serverBaseUrl.replace(/\/+$/, "") + "/" + topic.replace(/^\/+/, "");

  const renderedDict =
    rendered && typeof rendered === "object" && !Array.isArray(rendered)
      ? rendered
      : {};

  let bodyVal = renderedDict.body ?? renderedDict.message ?? renderedDict.text;
  let body = bodyVal != null ? coerceHeaderValue(bodyVal) : null;
  if (body == null) body = message.body || "";

  const headers = {};

  const defaultHeaders = channelConfig.default_headers_json;
  if (defaultHeaders && typeof defaultHeaders === "object") {
    for (const [k, v] of Object.entries(defaultHeaders)) {
      const kk = String(k).trim();
      const vv = coerceHeaderValue(v);
      if (kk && vv != null) headers[kk] = vv;
    }
  }

  const title = coerceHeaderValue(renderedDict.title);
  if (title != null) {
    headers.Title = headers.Title || title;
  } else if (message.title) {
    headers.Title = headers.Title || message.title;
  }

  const tags = renderedDict.tags;
  if (Array.isArray(tags)) {
    const joined = tags
      .map((x) => String(x).trim())
      .filter(Boolean)
      .join(",");
    if (joined) headers.Tags = headers.Tags || joined;
  } else {
    const t = coerceHeaderValue(tags);
    if (t != null) {
      headers.Tags = headers.Tags || t;
    } else if (Array.isArray(message.tags) && message.tags.length > 0) {
      const joined = message.tags
        .map((x) => String(x).trim())
        .filter(Boolean)
        .join(",");
      if (joined) headers.Tags = headers.Tags || joined;
    }
  }

  const prio = coerceHeaderValue(renderedDict.priority);
  if (prio != null) {
    headers.Priority = headers.Priority || prio;
  } else if (message.priority && message.priority !== 3) {
    const ntfyPrio = PRIORITY_MAP[message.priority];
    if (ntfyPrio) headers.Priority = headers.Priority || ntfyPrio;
  }

  const click = coerceHeaderValue(renderedDict.click);
  if (click != null) headers.Click = headers.Click || click;

  const icon = coerceHeaderValue(renderedDict.icon);
  if (icon != null) headers.Icon = headers.Icon || icon;

  const attach = coerceHeaderValue(renderedDict.attach);
  if (attach != null) headers.Attach = headers.Attach || attach;

  if (typeof renderedDict.markdown === "boolean" && renderedDict.markdown) {
    headers.Markdown = headers.Markdown || "true";
  }

  const token = (channelConfig.access_token || "").trim();
  if (token) headers.Authorization = headers.Authorization || `Bearer ${token}`;

  const username = (channelConfig.username || "").trim();
  const password = (channelConfig.password || "").trim();
  const auth =
    username && password && !token
      ? "Basic " + btoa(username + ":" + password)
      : null;
  if (auth) headers.Authorization = headers.Authorization || auth;

  return { url, body, headers };
}

export async function sendNtfyPublish({ url, body, headers }) {
  const resp = await fetch(url, {
    method: "POST",
    body: body,
    headers: headers,
  });
  return { ok: resp.status >= 200 && resp.status < 300, status: resp.status };
}
