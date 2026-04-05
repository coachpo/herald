export type JsonObjectParseResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; error: string };

function parseNonEmptyJsonObject(text: string): JsonObjectParseResult {
  try {
    const value = JSON.parse(text) as unknown;
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { ok: false, error: "JSON must be an object." };
    }
    return { ok: true, value: value as Record<string, unknown> };
  } catch {
    return { ok: false, error: "Invalid JSON." };
  }
}

export function parseOptionalJsonObject(text: string): JsonObjectParseResult {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: {} };
  return parseNonEmptyJsonObject(trimmed);
}

export function parseRequiredJsonObject(text: string): JsonObjectParseResult {
  const trimmed = text.trim();
  if (!trimmed) return { ok: false, error: "JSON is required." };
  return parseNonEmptyJsonObject(trimmed);
}
