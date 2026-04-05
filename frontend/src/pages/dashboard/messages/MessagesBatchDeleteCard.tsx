import type { IngestEndpoint } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface MessagesBatchDeleteCardProps {
  endpoints: IngestEndpoint[];
  canMutate: boolean;
  olderThanDays: number;
  setOlderThanDays: (value: number) => void;
  batchEndpointId: string;
  setBatchEndpointId: (value: string) => void;
  batchMessage: string | null;
  onDelete: () => void;
}

export function MessagesBatchDeleteCard({
  endpoints,
  canMutate,
  olderThanDays,
  setOlderThanDays,
  batchEndpointId,
  setBatchEndpointId,
  batchMessage,
  onDelete,
}: MessagesBatchDeleteCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-sm font-semibold">Batch delete</div>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="batch-days">Older than (days)</Label>
          <Input
            id="batch-days"
            type="number"
            className="w-24"
            value={olderThanDays}
            onChange={(e) => setOlderThanDays(Number(e.target.value))}
            min={1}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="batch-ep">Endpoint (optional)</Label>
          <select
            id="batch-ep"
            className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
            value={batchEndpointId}
            onChange={(e) => setBatchEndpointId(e.target.value)}
          >
            <option value="">All endpoints</option>
            {endpoints.map((ep) => (
              <option key={ep.id} value={ep.id}>{ep.name}</option>
            ))}
          </select>
        </div>
        <Button variant="destructive" disabled={!canMutate} onClick={onDelete}>
          Delete
        </Button>
      </div>
      {batchMessage && <div className="mt-2 text-sm text-muted-foreground">{batchMessage}</div>}
    </div>
  );
}
