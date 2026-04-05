import type { IngestEndpoint } from "@/lib/types";

export interface CreateResp {
  endpoint: IngestEndpoint;
  ingest_key: string;
  ingest_url: string;
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {}

  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.position = "fixed";
    el.style.left = "-9999px";
    el.style.top = "0";
    document.body.appendChild(el);
    el.focus();
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

export function buildIngestCurl(created: CreateResp): string {
  return `curl -X POST '${created.ingest_url}' -H 'X-Herald-Ingest-Key: ${created.ingest_key}' -H 'Content-Type: application/json' --data '{"body":"hello"}'`;
}
