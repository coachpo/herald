export function constantTimeEqual(a, b) {
  const aa = String(a || "");
  const bb = String(b || "");
  if (aa.length !== bb.length) return false;
  let out = 0;
  for (let i = 0; i < aa.length; i++) out |= aa.charCodeAt(i) ^ bb.charCodeAt(i);
  return out === 0;
}

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function timingSafeEqualStrings(a, b) {
  const sa = String(a || "");
  const sb = String(b || "");
  if (!sa || !sb) return false;
  const [da, db] = await Promise.all([sha256Hex(sa), sha256Hex(sb)]);
  return constantTimeEqual(da, db);
}

export async function authenticateIngest(config, endpointId, rawKey) {
  const wanted = String(endpointId || "").replace(/-/g, "");
  const endpoint = (config?.ingest_endpoints || []).find(
    (ep) => String(ep.id).replace(/-/g, "") === wanted,
  );
  if (!endpoint || !rawKey) return null;
  const digest = await sha256Hex(String(rawKey).trim());
  return constantTimeEqual(digest, endpoint.key_sha256) ? endpoint : null;
}
