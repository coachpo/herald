import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { IngestEndpoint } from "@/lib/types";

export interface EndpointListCardProps {
  loading: boolean;
  endpoints: IngestEndpoint[];
  canCreate: boolean;
  copiedEndpointId: string | null;
  onCopyUrl: (endpointId: string, url: string) => void;
  onRevoke: (endpointId: string) => void;
  onArchive: (endpointId: string) => void;
  buildUrl: (endpointId: string) => string;
}

export function EndpointListCard({
  loading,
  endpoints,
  canCreate,
  copiedEndpointId,
  onCopyUrl,
  onRevoke,
  onArchive,
  buildUrl,
}: EndpointListCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3 text-sm font-semibold">Endpoints</div>
      {loading ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">Loading...</div>
      ) : endpoints.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">No endpoints yet.</div>
      ) : (
        <div className="divide-y divide-border">
          {endpoints.map((endpoint) => {
            const revoked = Boolean(endpoint.revoked_at);
            const ingestUrl = buildUrl(endpoint.id);
            return (
              <div key={endpoint.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="text-sm font-medium text-foreground">{endpoint.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Created: {new Date(endpoint.created_at).toLocaleString()} · Last used:{" "}
                    {endpoint.last_used_at ? new Date(endpoint.last_used_at).toLocaleString() : "never"}
                    {revoked && (
                      <Badge variant="destructive" className="ml-2 uppercase text-[10px] tracking-wide">
                        Revoked
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium">URL:</span>
                    <span className="break-all rounded-lg border border-border bg-muted px-2 py-1 font-mono text-[11px] text-foreground">
                      {ingestUrl}
                    </span>
                    <Button
                      type="button"
                      size="xs"
                      variant="outline"
                      className={
                        copiedEndpointId === endpoint.id
                          ? "border-success/30 bg-success/20 text-success"
                          : "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
                      }
                      onClick={() => onCopyUrl(endpoint.id, ingestUrl)}
                    >
                      {copiedEndpointId === endpoint.id ? "Copied" : "Copy"}
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    disabled={revoked || !canCreate}
                    onClick={() => onRevoke(endpoint.id)}
                  >
                    Revoke
                  </Button>
                  <Button
                    variant="outline"
                    size="xs"
                    disabled={!canCreate}
                    onClick={() => onArchive(endpoint.id)}
                  >
                    Archive
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
