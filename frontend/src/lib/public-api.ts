function isProbablyLocalhost(hostname: string): boolean {
  const h = (hostname || "").toLowerCase();
  return h === "localhost" || h === "127.0.0.1" || h === "::1";
}

function normalizePublicApiUrl(raw: string): URL {
  const s = (raw || "").trim();
  if (!s) return new URL(window.location.origin);

  const withScheme = /^https?:\/\//i.test(s) ? s : `https://${s}`;
  const url = new URL(withScheme);

  if (url.protocol === "http:" && !isProbablyLocalhost(url.hostname)) {
    url.protocol = "https:";
  }

  url.username = "";
  url.password = "";
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url;
}

function getPublicApiOrigin(): string {
  const url = normalizePublicApiUrl(import.meta.env.VITE_API_URL ?? "");
  return url.origin;
}

export function buildPublicApiUrl(path: string): string {
  const p = (path || "").trim();
  if (!p) throw new Error("path is required");
  if (/^https?:\/\//i.test(p)) return p;

  const origin = getPublicApiOrigin();
  const pathname = p.startsWith("/") ? p : `/${p}`;
  return new URL(pathname, origin).toString();
}

export function uuidToHex(id: string): string | null {
  const s = (id || "").trim();
  if (!s) return null;
  if (/^[0-9a-f]{32}$/i.test(s)) return s.toLowerCase();
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)) {
    return s.replace(/-/g, "").toLowerCase();
  }
  return null;
}

export function buildIngestUrl(endpointId: string): string {
  const hex = uuidToHex(endpointId) ?? endpointId;
  return buildPublicApiUrl(`/api/ingest/${hex}`);
}
