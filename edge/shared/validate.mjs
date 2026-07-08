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
  if (json.priority != null) {
    const p = Number(json.priority);
    if (!Number.isInteger(p) || p < 1 || p > 5) {
      return { ok: false, error: "invalid_priority" };
    }
  }
  if (json.tags != null && !Array.isArray(json.tags)) {
    return { ok: false, error: "invalid_tags" };
  }
  if (json.url != null && typeof json.url !== "string") {
    return { ok: false, error: "invalid_url" };
  }
  if (json.extras != null && (typeof json.extras !== "object" || Array.isArray(json.extras))) {
    return { ok: false, error: "invalid_extras" };
  }

  return { ok: true };
}
