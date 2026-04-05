import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";
import type { Delivery, MessageDetail } from "@/lib/types";
import { priorityBadgeClass } from "./messages/utils";

const deliveryStatusBadgeClass: Record<Delivery["status"], string> = {
  queued: "border-border bg-card text-muted-foreground",
  sending: "border-info/20 bg-info/10 text-info",
  retry: "border-warning/20 bg-warning/10 text-warning",
  sent: "border-success/20 bg-success/10 text-success",
  failed: "border-destructive/20 bg-destructive/10 text-destructive",
};

export default function MessageDetailPage() {
  const auth = useAuth();
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";
  const [msg, setMsg] = useState<MessageDetail | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canDelete = Boolean(auth.user?.email_verified_at);
  const [wrapBody, setWrapBody] = useState(true);

  useEffect(() => {
    (async () => {
      if (!id) {
        setError("Missing message id.");
        setLoading(false);
        return;
      }

      if (!auth.accessToken) {
        setLoading(true);
        return;
      }

      setLoading(true);
      setError(null);
      const [mRes, dRes] = await Promise.all([
        authedFetch(auth, `/api/messages/${id}`, { method: "GET" }),
        authedFetch(auth, `/api/messages/${id}/deliveries`, { method: "GET" }),
      ]);
      if (!mRes.ok) {
        setError((await readApiError(mRes)).message);
        setLoading(false);
        return;
      }
      if (!dRes.ok) {
        setError((await readApiError(dRes)).message);
        setLoading(false);
        return;
      }
      const mData = await readJson<{ message: MessageDetail }>(mRes);
      const dData = await readJson<{ deliveries: Delivery[] }>(dRes);
      setMsg(mData.message);
      setDeliveries(dData.deliveries);
      setLoading(false);
    })();
  }, [auth, id]);

  if (loading) return <div className="text-sm text-muted-foreground">Loading...</div>;
  if (error) {
    return (
      <div className="space-y-4">
        <div className="text-lg font-semibold tracking-tight">Message</div>
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      </div>
    );
  }
  if (!msg) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold tracking-tight">Message detail</div>
        {canDelete && !msg.deleted_at && (
          <button
            className="rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
            onClick={async () => {
              if (!confirm("Soft-delete this message?")) return;
              const res = await authedFetch(auth, `/api/messages/${id}`, { method: "DELETE" });
              if (!res.ok) {
                setError((await readApiError(res)).message);
                return;
              }
              setMsg((prev) => (prev ? { ...prev, deleted_at: new Date().toISOString() } : prev));
            }}
          >
            Delete
          </button>
        )}
      </div>

      {msg.deleted_at && (
        <div className="rounded-xl border border-warning/20 bg-warning/10 px-3 py-2 text-sm text-warning">
          Soft-deleted at {new Date(msg.deleted_at).toLocaleString()}.
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card">
        <div className="divide-y divide-border text-sm">
          <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
            <div className="font-medium text-muted-foreground">ID</div>
            <div className="font-mono text-xs break-all">{msg.id}</div>
          </div>
          <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
            <div className="font-medium text-muted-foreground">Endpoint</div>
            <div className="font-mono text-xs break-all">{msg.ingest_endpoint_id}</div>
          </div>
          <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
            <div className="font-medium text-muted-foreground">Received</div>
            <div>{new Date(msg.received_at).toLocaleString()}</div>
          </div>
          <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
            <div className="font-medium text-muted-foreground">Priority</div>
            <div>
              <span
                className={
                  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold " +
                  priorityBadgeClass(msg.priority)
                }
              >
                {msg.priority}
              </span>
            </div>
          </div>
          {msg.title && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">Title</div>
              <div>{msg.title}</div>
            </div>
          )}
          {msg.tags.length > 0 && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">Tags</div>
              <div className="flex flex-wrap gap-1">
                {msg.tags.map((t) => (
                  <span key={t} className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium text-foreground">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {msg.group && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">Group</div>
              <div>{msg.group}</div>
            </div>
          )}
          {msg.url && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">URL</div>
              <div className="break-all text-xs">{msg.url}</div>
            </div>
          )}
          <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
            <div className="font-medium text-muted-foreground">Remote IP</div>
            <div className="font-mono text-xs">{msg.remote_ip}</div>
          </div>
          {msg.user_agent && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">User-Agent</div>
              <div className="break-all text-xs">{msg.user_agent}</div>
            </div>
          )}
          {msg.content_type && (
            <div className="grid grid-cols-[8rem_1fr] px-4 py-2">
              <div className="font-medium text-muted-foreground">Content-Type</div>
              <div className="text-xs">{msg.content_type}</div>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="text-sm font-semibold">Body</div>
          <button
            className="rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted"
            onClick={() => setWrapBody((v) => !v)}
          >
            {wrapBody ? "No wrap" : "Wrap"}
          </button>
        </div>
        <pre
          className={
            "px-4 py-3 font-mono text-xs " +
            (wrapBody ? "whitespace-pre-wrap break-words" : "overflow-x-auto whitespace-pre")
          }
        >
          {msg.body}
        </pre>
      </div>

      {Object.keys(msg.extras).length > 0 && (
        <div className="rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-semibold">Extras</div>
          <pre className="whitespace-pre-wrap break-words px-4 py-3 font-mono text-xs">
            {JSON.stringify(msg.extras, null, 2)}
          </pre>
        </div>
      )}

      {Object.keys(msg.headers).length > 0 && (
        <div className="rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-semibold">Headers</div>
          <pre className="whitespace-pre-wrap break-words px-4 py-3 font-mono text-xs">
            {JSON.stringify(msg.headers, null, 2)}
          </pre>
        </div>
      )}

      {Object.keys(msg.query).length > 0 && (
        <div className="rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-semibold">Query params</div>
          <pre className="whitespace-pre-wrap break-words px-4 py-3 font-mono text-xs">
            {JSON.stringify(msg.query, null, 2)}
          </pre>
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3 text-sm font-semibold">
          Deliveries ({deliveries.length})
        </div>
        {deliveries.length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">No deliveries.</div>
        ) : (
          <div className="divide-y divide-border">
            {deliveries.map((d) => (
              <div key={d.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">
                    <span
                      className={
                        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide " +
                        deliveryStatusBadgeClass[d.status]
                      }
                    >
                      {d.status}
                    </span>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Rule: {d.rule_name ?? d.rule_id} | Channel: {d.channel_name ?? d.channel_id}
                    </div>
                  </div>
                  <div className="text-right text-xs text-muted-foreground">
                    <div>attempts {d.attempt_count}</div>
                    {d.next_attempt_at && <div>next: {new Date(d.next_attempt_at).toLocaleString()}</div>}
                    {d.sent_at && <div>sent: {new Date(d.sent_at).toLocaleString()}</div>}
                  </div>
                </div>
                {d.last_error && (
                  <div className="mt-1 text-xs text-destructive">{d.last_error}</div>
                )}
                {d.provider_response != null && (
                  <pre className="mt-2 whitespace-pre-wrap break-words rounded-xl border border-border bg-muted p-3 font-mono text-xs">
                    {JSON.stringify(d.provider_response, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
