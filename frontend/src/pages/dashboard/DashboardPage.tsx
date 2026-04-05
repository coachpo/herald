import { Link } from "react-router";
import { useCallback, useEffect, useMemo, useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { authedFetch } from "@/lib/authed";
import { useAuth } from "@/lib/auth";
import type { IngestEndpoint, MessageSummary } from "@/lib/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { priorityBadgeClass } from "./messages/utils";

export default function DashboardPage() {
  const auth = useAuth();
  const { user } = auth;
  const verified = Boolean(user?.email_verified_at);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageSummary[]>([]);
  const [endpoints, setEndpoints] = useState<IngestEndpoint[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [mRes, eRes] = await Promise.all([
      authedFetch(auth, "/api/messages", { method: "GET" }),
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
    setMessages(mData.messages.slice(0, 8));
    setEndpoints(eData.endpoints);
    setLoading(false);
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const endpointNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const ep of endpoints) {
      map.set(ep.id, ep.name);
    }
    return map;
  }, [endpoints]);

  const recentFailures = useMemo(
    () => messages.filter((m) => m.deliveries.failed > 0).slice(0, 5),
    [messages],
  );

  return (
    <div className="space-y-6">
      {!verified && (
        <div className="rounded-2xl border border-warning/20 bg-warning/10 px-4 py-3 text-sm text-warning">
          Your email is not verified. Create actions are disabled until you verify.
          <div className="mt-2">
            <Link className="font-medium underline" to="/account">
              Go to account settings
            </Link>
          </div>
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div>
        <div className="text-lg font-semibold tracking-tight">Quick actions</div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <Link
            to="/ingest-endpoints"
            className="rounded-2xl border border-border bg-muted px-4 py-4 hover:bg-muted/80"
          >
            <div className="text-sm font-semibold">Create ingest endpoint</div>
            <div className="mt-1 text-xs text-muted-foreground">Tokenized URL for scripts/services.</div>
          </Link>
          <Link
            to="/channels"
            className="rounded-2xl border border-border bg-muted px-4 py-4 hover:bg-muted/80"
          >
            <div className="text-sm font-semibold">Create channel</div>
            <div className="mt-1 text-xs text-muted-foreground">Point at Bark, ntfy, or MQTT.</div>
          </Link>
          <Link
            to="/rules"
            className="rounded-2xl border border-border bg-muted px-4 py-4 hover:bg-muted/80"
          >
            <div className="text-sm font-semibold">Create rule</div>
            <div className="mt-1 text-xs text-muted-foreground">Match messages and forward.</div>
          </Link>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3 text-sm font-semibold">Recent messages</div>
        {loading ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Loading...</div>
        ) : messages.length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">No messages yet.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Endpoint</TableHead>
                <TableHead>Title / Body</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Tags</TableHead>
                <TableHead>Group</TableHead>
                <TableHead>Deliveries</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {messages.map((m) => {
                const d = m.deliveries;
                const pending = d.queued + d.sending + d.retry;
                const titleOrPreview = (m.title || "").trim() || m.body_preview;
                return (
                  <TableRow key={m.id}>
                    <TableCell className="whitespace-normal text-xs text-muted-foreground">
                      {new Date(m.received_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="whitespace-normal text-xs text-muted-foreground">
                      {endpointNameById.get(m.ingest_endpoint_id) ?? m.ingest_endpoint_id}
                    </TableCell>
                    <TableCell className="max-w-[16rem] truncate">
                      <Link
                        to={`/messages/${m.id}`}
                        className="text-sm text-primary hover:underline"
                      >
                        {titleOrPreview}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <span
                        className={
                          "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold " +
                          priorityBadgeClass(m.priority)
                        }
                      >
                        {m.priority}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[14rem] whitespace-normal">
                      {m.tags.length === 0 ? (
                        <span className="text-xs text-muted-foreground">-</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {m.tags.map((t) => (
                            <span
                              key={`${m.id}-${t}`}
                              className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium text-foreground"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-normal text-xs text-muted-foreground">
                      {m.group || "-"}
                    </TableCell>
                    <TableCell className="whitespace-normal text-xs text-muted-foreground">
                      <span className="text-success">sent {d.sent}</span> ·{" "}
                      <span className="text-destructive">failed {d.failed}</span> ·{" "}
                      <span className={pending > 0 ? "text-warning" : "text-muted-foreground"}>pending {pending}</span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card px-4 py-4">
        <div className="text-sm font-semibold">Recent failures</div>
        {loading ? (
          <div className="mt-2 text-sm text-muted-foreground">Loading...</div>
        ) : recentFailures.length === 0 ? (
          <div className="mt-2 text-sm text-muted-foreground">No recent failures.</div>
        ) : (
          <div className="mt-3 space-y-2">
            {recentFailures.map((m) => (
              <Link
                key={m.id}
                to={`/messages/${m.id}`}
                className="block rounded-xl border border-border bg-muted px-3 py-2 hover:bg-muted/70"
              >
                <div className="text-sm font-medium text-foreground">
                  {endpointNameById.get(m.ingest_endpoint_id) ?? m.ingest_endpoint_id}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {new Date(m.received_at).toLocaleString()} · failed {m.deliveries.failed}
                </div>
                <div className="mt-1 truncate text-xs text-muted-foreground">
                  {(m.title || "").trim() || m.body_preview}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card px-4 py-4">
        <div className="text-sm font-semibold">Getting started</div>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
          <li>Create an ingest endpoint.</li>
          <li>POST JSON to the ingest URL (minimum: {`{"body":"..."}`}).</li>
          <li>Create a Bark channel and a rule to forward messages.</li>
        </ol>
      </div>
    </div>
  );
}
