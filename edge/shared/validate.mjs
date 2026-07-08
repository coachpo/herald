export function parseIngestEndpointIdFromPath(pathname) {
  const parts = String(pathname || "")
    .split("/")
    .filter(Boolean);
  if (parts.length !== 3) return "";
  if (parts[0] !== "api" || parts[1] !== "ingest") return "";
  return parts[2];
}

export function validatePayload(json) {
  if (typeof json !== "object" || json === null || Array.isArray(json)) {
    return { ok: false, error: "invalid_json_object" };
  }

  const allowed = new Set(["body", "title", "group", "priority", "tags", "url", "extras"]);
  for (const key of Object.keys(json)) {
    if (!allowed.has(key)) return { ok: false, error: `unknown_field:${key}` };
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
  if (Object.hasOwn(json, "priority")) {
    if (
      typeof json.priority !== "number" ||
      !Number.isInteger(json.priority) ||
      json.priority < 1 ||
      json.priority > 5
    ) {
      return { ok: false, error: "invalid_priority" };
    }
  }
  if (Object.hasOwn(json, "tags")) {
    if (!Array.isArray(json.tags) || json.tags.some((tag) => typeof tag !== "string")) {
      return { ok: false, error: "invalid_tags" };
    }
  }
  if (json.url != null) {
    if (typeof json.url !== "string") return { ok: false, error: "invalid_url" };
    const trimmedUrl = json.url.trim();
    if (trimmedUrl) {
      try {
        if (!/^https?:\/\/[^/?#]+/i.test(trimmedUrl)) return { ok: false, error: "invalid_url" };
        const parsed = new URL(trimmedUrl);
        if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) {
          return { ok: false, error: "invalid_url" };
        }
      } catch {
        return { ok: false, error: "invalid_url" };
      }
    }
  }
  if (Object.hasOwn(json, "extras")) {
    if (typeof json.extras !== "object" || json.extras === null || Array.isArray(json.extras)) {
      return { ok: false, error: "invalid_extras" };
    }
    if (Object.values(json.extras).some((value) => typeof value !== "string")) {
      return { ok: false, error: "invalid_extras" };
    }
  }

  return { ok: true };
}
