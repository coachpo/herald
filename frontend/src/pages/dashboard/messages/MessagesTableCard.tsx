import { Link } from "react-router";

import type { MessageSummary } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { priorityBadgeClass } from "./utils";

export interface MessagesTableCardProps {
  loading: boolean;
  items: MessageSummary[];
  endpointNameById: Map<string, string>;
}

export function MessagesTableCard({
  loading,
  items,
  endpointNameById,
}: MessagesTableCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card">
      {loading ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">Loading...</div>
      ) : items.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">No messages found.</div>
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
            {items.map((message) => {
              const deliveries = message.deliveries;
              const pending = deliveries.queued + deliveries.sending + deliveries.retry;
              const titleOrPreview = (message.title || "").trim() || message.body_preview;
              return (
                <TableRow key={message.id}>
                  <TableCell className="whitespace-normal text-xs text-muted-foreground">
                    {new Date(message.received_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="whitespace-normal text-xs text-muted-foreground">
                    {endpointNameById.get(message.ingest_endpoint_id) ?? message.ingest_endpoint_id}
                  </TableCell>
                  <TableCell className="max-w-[16rem] truncate">
                    <Link to={`/messages/${message.id}`} className="text-sm text-primary hover:underline">
                      {titleOrPreview}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span
                      className={
                        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold " +
                        priorityBadgeClass(message.priority)
                      }
                    >
                      {message.priority}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-[14rem] whitespace-normal">
                    {message.tags.length === 0 ? (
                      <span className="text-xs text-muted-foreground">-</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {message.tags.map((tag) => (
                          <span
                            key={`${message.id}-${tag}`}
                            className="rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium text-foreground"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-normal text-xs text-muted-foreground">
                    {message.group || "-"}
                  </TableCell>
                  <TableCell className="whitespace-normal text-xs text-muted-foreground">
                    <span className="text-success">sent {deliveries.sent}</span> ·{" "}
                    <span className="text-destructive">failed {deliveries.failed}</span> ·{" "}
                    <span className={pending > 0 ? "text-warning" : "text-muted-foreground"}>
                      pending {pending}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
