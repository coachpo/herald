import { useCallback, useEffect, useMemo, useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";
import type { IngestEndpoint, MessageSummary } from "@/lib/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { MessagesBatchDeleteCard } from "./messages/MessagesBatchDeleteCard";
import { MessagesFiltersCard } from "./messages/MessagesFiltersCard";
import { MessagesTableCard } from "./messages/MessagesTableCard";

export default function MessagesPage() {
  const auth = useAuth();

  const [items, setItems] = useState<MessageSummary[]>([]);
  const [endpoints, setEndpoints] = useState<IngestEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterEndpointId, setFilterEndpointId] = useState("");
  const [priorityMin, setPriorityMin] = useState("");
  const [priorityMax, setPriorityMax] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const canMutate = Boolean(auth.user?.email_verified_at);
  const [olderThanDays, setOlderThanDays] = useState(30);
  const [batchEndpointId, setBatchEndpointId] = useState("");
  const [batchMessage, setBatchMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (filterEndpointId) params.set("ingest_endpoint_id", filterEndpointId);
    if (priorityMin) params.set("priority_min", priorityMin);
    if (priorityMax) params.set("priority_max", priorityMax);
    if (fromDate) params.set("from", fromDate);
    if (toDate) params.set("to", toDate);

    const [mRes, eRes] = await Promise.all([
      authedFetch(auth, `/api/messages?${params.toString()}`, { method: "GET" }),
      authedFetch(auth, "/api/ingest-endpoints", { method: "GET" }),
    ]);

    if (!mRes.ok) {
      setError((await readApiError(mRes)).message);
      setLoading(false);
      return;
    }
    if (!eRes.ok) {
      setError((await readApiError(eRes)).message);
      setLoading(false);
      return;
    }

    const mData = await readJson<{ messages: MessageSummary[] }>(mRes);
    const eData = await readJson<{ endpoints: IngestEndpoint[] }>(eRes);
    setItems(mData.messages);
    setEndpoints(eData.endpoints);
    setLoading(false);
  }, [auth, filterEndpointId, priorityMin, priorityMax, fromDate, toDate]);

  useEffect(() => {
    void load();
  }, [load]);

  const endpointNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const ep of endpoints) map.set(ep.id, ep.name);
    return map;
  }, [endpoints]);

  return (
    <div className="space-y-6">
      <div>
        <div className="text-lg font-semibold tracking-tight">Messages</div>
        <div className="mt-1 text-sm text-muted-foreground">All ingested messages.</div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <MessagesFiltersCard
        endpoints={endpoints}
        filterEndpointId={filterEndpointId}
        setFilterEndpointId={setFilterEndpointId}
        priorityMin={priorityMin}
        setPriorityMin={setPriorityMin}
        priorityMax={priorityMax}
        setPriorityMax={setPriorityMax}
        fromDate={fromDate}
        setFromDate={setFromDate}
        toDate={toDate}
        setToDate={setToDate}
        onSubmit={() => void load()}
      />

      <MessagesBatchDeleteCard
        endpoints={endpoints}
        canMutate={canMutate}
        olderThanDays={olderThanDays}
        setOlderThanDays={setOlderThanDays}
        batchEndpointId={batchEndpointId}
        setBatchEndpointId={setBatchEndpointId}
        batchMessage={batchMessage}
        onDelete={async () => {
          if (!confirm(`Delete messages older than ${olderThanDays} days?`)) return;
          setBatchMessage(null);
          const body: Record<string, unknown> = { older_than_days: olderThanDays };
          if (batchEndpointId) body.ingest_endpoint_id = batchEndpointId;
          const res = await authedFetch(auth, "/api/messages/batch-delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          if (!res.ok) {
            setBatchMessage((await readApiError(res)).message);
            return;
          }
          const data = await readJson<{ deleted_count: number }>(res);
          setBatchMessage(`Deleted ${data.deleted_count} message(s).`);
          void load();
        }}
      />

      <MessagesTableCard loading={loading} items={items} endpointNameById={endpointNameById} />
    </div>
  );
}
