const PERMANENT_STATUSES = new Set([400, 401, 403, 404, 413, 415, 422]);
const UUID_RE = /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i;

export const MAX_PENDING_AGE_MS = 7 * 24 * 3600 * 1000;

export function backoffSeconds(attempts) {
  return Math.min(3600, 5 * 2 ** Math.max(attempts - 1, 0));
}

export function parseRelayHeaders(request) {
  const rawId = (request.headers.get("X-Herald-Message-Id") || "").trim();
  const receivedAt = (request.headers.get("X-Herald-Received-At") || "").trim();
  const via = (request.headers.get("X-Herald-Relay-Via") || "")
    .toLowerCase().replace(/[^a-z,]/g, "").slice(0, 64);
  return {
    id: UUID_RE.test(rawId) ? rawId.toLowerCase() : null,
    receivedAt: Number.isFinite(Date.parse(receivedAt)) ? receivedAt : null,
    via: via || null,
  };
}

export function buildEnvelope({ endpointId, rawKey, body, via, nowIso, id, receivedAt }) {
  return {
    id: id || crypto.randomUUID(),
    endpoint_id: endpointId,
    received_at: receivedAt || nowIso,
    via,
    ingest_key: rawKey,
    body,
    attempts: 0,
    last_error: null,
  };
}

export async function forwardEnvelope(envelope, upstreamUrl, fetchImpl = fetch) {
  const url = `${String(upstreamUrl).replace(/\/+$/, "")}/api/ingest/${envelope.endpoint_id}`;
  try {
    const res = await fetchImpl(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Herald-Ingest-Key": envelope.ingest_key,
        "X-Herald-Message-Id": envelope.id,
        "X-Herald-Received-At": envelope.received_at,
        "X-Herald-Relay-Via": envelope.via,
      },
      body: envelope.body,
    });
    if (res.ok) return { ok: true };
    return {
      ok: false,
      permanent: PERMANENT_STATUSES.has(res.status),
      error: `upstream_status_${res.status}`,
    };
  } catch (err) {
    return { ok: false, permanent: false, error: String(err).slice(0, 200) };
  }
}
