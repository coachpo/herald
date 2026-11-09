import { useEffect, useRef } from "react";
import type { Message } from "../lib/types";
import { dateTime, deliveryLabels, deliverySummary } from "../lib/presentation";
import { Icon } from "./Icon";

interface MessageDetailProps {
  readonly message: Message;
  readonly opened: boolean;
  readonly onBack: () => void;
  readonly retrying: string | null;
  readonly onRetry: (id: string) => void;
}

export function MessageDetail({
  message,
  opened,
  onBack,
  retrying,
  onRetry,
}: MessageDetailProps) {
  const summary = deliverySummary(message);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (opened) title.current?.focus({ preventScroll: true });
  }, [opened, message.id]);
  return (
    <section className="message-detail" aria-label="Message detail">
      <button className="ghost back-to-list" onClick={onBack}>
        <Icon name="back" />
        Back to messages
      </button>
      <div className="detail-heading">
        <span className={`status ${summary.tone}`}>{summary.label}</span>
        <span className="small muted">Priority {message.priority}</span>
      </div>
      <h2 ref={title} tabIndex={-1} className="message-title">
        {message.title || "Untitled message"}
      </h2>
      <p className="small muted">
        Received{" "}
        <time dateTime={message.received_at}>
          {dateTime(message.received_at)}
        </time>
      </p>
      <div className="receipt-rail" aria-label="Receipt and delivery progress">
        <div>
          <Icon name="check" />
          <strong>Received</strong>
          <span>Stored safely</span>
        </div>
        <div>
          <Icon name="inbox" />
          <strong>Delivery queue</strong>
          <span>
            {summary.total} target{summary.total === 1 ? "" : "s"}
          </span>
        </div>
        <div
          className={
            summary.sent === summary.total && summary.total > 0
              ? "complete"
              : ""
          }
        >
          <Icon
            name={
              summary.sent === summary.total && summary.total > 0
                ? "check"
                : summary.failed
                  ? "alert"
                  : "clock"
            }
          />
          <strong>Delivered</strong>
          <span>
            {summary.sent} of {summary.total}
          </span>
        </div>
      </div>
      <section className="detail-body">
        <h3>Message</h3>
        <p className="message-body">{message.body}</p>
      </section>
      <section className="routing-decision stack" aria-label="Routing decision">
        <h3>Routing decision</h3>
        {message.routing_decision ? (
          <>
            <p>
              Selection: {message.routing_decision.mode === "explicit"
                ? "Explicit targets"
                : message.routing_decision.mode === "rules"
                  ? "Matching rules"
                  : "Default fallback (no matching rules)"}
            </p>
            <p className="small muted">
              Rules revision: {message.routing_decision.rules_revision ?? "Not applicable (explicit selection)"}
            </p>
            <p className="small muted">
              Matched rule IDs: {message.routing_decision.matched_rule_ids.length === 0 ? "None" : message.routing_decision.matched_rule_ids.map((id, index) => (
                <span key={id}>{index > 0 ? ", " : ""}<code>{id}</code></span>
              ))}
            </p>
            <p className="small muted">Recorded at receipt. Rule IDs and version are an explanation, not a historical copy of rule or target configuration. Final targets and current delivery states appear below.</p>
          </>
        ) : (
          <p className="small muted">No routing decision was recorded for this message.</p>
        )}
      </section>
      <section className="delivery-results">
        <div className="section-heading">
          <h3>Delivery results</h3>
          <span className="small muted">
            {summary.sent} of {summary.total} delivered
          </span>
        </div>
        <div className="deliveries">
          {message.deliveries.map((delivery) => (
            <article className="delivery" key={delivery.id}>
              <div className="section-heading">
                <h4>{delivery.target_name}</h4>
                <span className={`status ${delivery.status}`}>
                  <Icon
                    name={
                      delivery.status === "sent"
                        ? "check"
                        : delivery.status === "failed"
                          ? "alert"
                          : "clock"
                    }
                    size={14}
                  />
                  {deliveryLabels[delivery.status]}
                </span>
              </div>
              <p className="small muted">
                {delivery.attempts} attempt{delivery.attempts === 1 ? "" : "s"}
                {delivery.completed_at
                  ? ` · Completed ${dateTime(delivery.completed_at)}`
                  : delivery.available_at && delivery.status === "retry"
                    ? ` · Next attempt ${dateTime(delivery.available_at)}`
                    : ""}
              </p>
              {delivery.last_error && (
                <p className="delivery-error">{delivery.last_error}</p>
              )}
              {delivery.status === "failed" && (
                <button
                  className="secondary"
                  disabled={retrying !== null}
                  onClick={() => onRetry(delivery.id)}
                >
                  <Icon name="refresh" />
                  {retrying === delivery.id
                    ? "Queuing…"
                    : "Retry failed delivery"}
                </button>
              )}
            </article>
          ))}
        </div>
      </section>
      <details className="message-identifiers">
        <summary>Message ID</summary>
        <code className="identifier">{message.id}</code>
      </details>
      <p className="small muted detail-note">
        Received confirms durable storage, not delivery. Only final failed
        deliveries can be retried manually.
      </p>
    </section>
  );
}
