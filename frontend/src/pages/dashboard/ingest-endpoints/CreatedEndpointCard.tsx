import { Button } from "@/components/ui/button";

import type { CreateResp } from "./utils";
import { buildIngestCurl } from "./utils";

export interface CreatedEndpointCardProps {
  created: CreateResp;
  copiedField: "key" | "url" | "curl" | null;
  onCopy: (field: "key" | "url" | "curl", text: string) => void;
  onDismiss: () => void;
}

export function CreatedEndpointCard({
  created,
  copiedField,
  onCopy,
  onDismiss,
}: CreatedEndpointCardProps) {
  const curl = buildIngestCurl(created);

  return (
    <div className="rounded-2xl border border-success/20 bg-success/10 p-4 dark:border-success/30 dark:bg-success/10">
      <div className="text-sm font-semibold text-success">Endpoint created</div>
      <div className="mt-2 grid min-w-0 gap-2 text-sm">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-medium text-success">Ingest key (copy now)</div>
            <Button
              type="button"
              size="xs"
              variant="outline"
              className={
                copiedField === "key"
                  ? "border-success/30 bg-success/20 text-success"
                  : "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
              }
              onClick={() => onCopy("key", created.ingest_key)}
            >
              {copiedField === "key" ? "Copied" : "Copy key"}
            </Button>
          </div>
          <div className="mt-1 max-w-full break-all rounded-xl border border-success/20 bg-card px-3 py-2 font-mono text-xs text-foreground">
            {created.ingest_key}
          </div>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-medium text-success">Ingest URL</div>
            <Button
              type="button"
              size="xs"
              variant="outline"
              className={
                copiedField === "url"
                  ? "border-success/30 bg-success/20 text-success"
                  : "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
              }
              onClick={() => onCopy("url", created.ingest_url)}
            >
              {copiedField === "url" ? "Copied" : "Copy URL"}
            </Button>
          </div>
          <div className="mt-1 max-w-full break-all rounded-xl border border-success/20 bg-card px-3 py-2 font-mono text-xs text-foreground">
            {created.ingest_url}
          </div>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-medium text-success">curl</div>
            <Button
              type="button"
              size="xs"
              variant="outline"
              className={
                copiedField === "curl"
                  ? "border-success/30 bg-success/20 text-success"
                  : "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
              }
              onClick={() => onCopy("curl", curl)}
            >
              {copiedField === "curl" ? "Copied" : "Copy curl"}
            </Button>
          </div>
          <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-all rounded-xl border border-success/20 bg-card px-3 py-2 font-mono text-xs text-foreground">
            {curl}
          </pre>
        </div>
      </div>
      <Button variant="outline" size="sm" className="mt-3" onClick={onDismiss}>
        Dismiss
      </Button>
    </div>
  );
}
