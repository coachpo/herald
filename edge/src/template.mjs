const VAR_RE = /\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g;

function lookup(path, ctx) {
  let cur = ctx;
  for (const part of path.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = cur[part];
  }
  return cur;
}

function renderStr(s, ctx) {
  return s.replace(VAR_RE, (_, path) => {
    const val = lookup(path, ctx);
    return val == null ? "" : String(val);
  });
}

export function renderTemplate(value, ctx) {
  if (typeof value === "string") return renderStr(value, ctx);
  if (Array.isArray(value)) return value.map((v) => renderTemplate(v, ctx));
  if (value !== null && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = renderTemplate(v, ctx);
    }
    return out;
  }
  return value;
}

export function buildTemplateContext(message, ingestEndpoint) {
  const tags = Array.isArray(message.tags) ? message.tags : [];
  const extras =
    message.extras && typeof message.extras === "object" ? message.extras : {};

  return {
    message: {
      id: String(message.id || ""),
      received_at: message.received_at || "",
      title: message.title || "",
      body: message.body || "",
      group: message.group || "",
      priority: String(message.priority ?? 3),
      tags: tags.map(String).join(","),
      url: message.url || "",
      extras: Object.fromEntries(
        Object.entries(extras).map(([k, v]) => [String(k), String(v)]),
      ),
    },
    request: {
      content_type: message.content_type || "",
      remote_ip: message.remote_ip || "",
      user_agent: message.user_agent || "",
      headers:
        message.headers && typeof message.headers === "object"
          ? message.headers
          : {},
      query:
        message.query && typeof message.query === "object" ? message.query : {},
    },
    ingest_endpoint: {
      id: String(ingestEndpoint.id || ""),
      name: ingestEndpoint.name || "",
    },
  };
}
