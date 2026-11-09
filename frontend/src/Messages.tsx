import { useRef, useState } from "react";
import type { MessageHistory } from "./hooks/useMessages";
import { dateTime, deliverySummary } from "./lib/presentation";
import { MessageDetail } from "./components/MessageDetail";
import { Feedback } from "./components/Feedback";
import { Icon } from "./components/Icon";

interface MessagesProps {
  readonly history: MessageHistory;
  readonly onCompose: () => void;
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
  readonly openSelected?: boolean;
}

export function Messages({
  history,
  onCompose,
  selectedId,
  onSelect,
  openSelected = false,
}: MessagesProps) {
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [detailOpen, setDetailOpen] = useState(openSelected);
  const listScroll = useRef(0);
  const selectedButton = useRef<HTMLButtonElement | null>(null);
  const { page, loading, error, refreshing, updatedAt } = history;
  const failures = page.messages.filter((message) =>
    message.deliveries.some((delivery) => delivery.status === "failed"),
  );
  const visible = onlyFailed ? failures : page.messages;
  const selected =
    visible.find((message) => message.id === selectedId) ?? visible[0];
  const back = () => {
    setDetailOpen(false);
    requestAnimationFrame(() => {
      window.scrollTo({ top: listScroll.current });
      selectedButton.current?.focus({ preventScroll: true });
    });
  };
  return (
    <main
      id="main-content"
      className={`messages-page${detailOpen ? " inspecting" : ""}`}
    >
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>
            <span className="list-title">Messages</span>
            <span className="inspection-title">Message detail</span>
          </h1>
          <p className="muted">Every receipt. Every delivery.</p>
        </div>
        <button onClick={onCompose}>
          <Icon name="plus" />
          New message
        </button>
      </div>
      <div className="history-toolbar">
        <div className="filter-tabs" aria-label="Message filters">
          <button
            aria-pressed={!onlyFailed}
            onClick={() => {
              setOnlyFailed(false);
              setDetailOpen(false);
            }}
          >
            All messages <span>{page.messages.length}</span>
          </button>
          <button
            aria-pressed={onlyFailed}
            onClick={() => {
              setOnlyFailed(true);
              setDetailOpen(false);
            }}
          >
            Failed on this page <span>{failures.length}</span>
          </button>
        </div>
        <button
          className="ghost refresh-button"
          aria-label="Refresh messages"
          onClick={() => void history.load()}
          disabled={refreshing}
        >
          <Icon name="refresh" />
          <span>{refreshing ? "Refreshing…" : "Refresh"}</span>
        </button>
      </div>
      <div className="history-meta small muted">
        <span>
          {loading
            ? "Loading messages…"
            : `${visible.length} message${visible.length === 1 ? "" : "s"} on this page`}
          {history.before ? " · Older history" : " · Latest history"}
        </span>
        <span>
          Updates every 4 seconds
          {updatedAt
            ? ` · ${updatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
            : ""}
        </span>
      </div>
      {error && (
        <Feedback tone="error" onRetry={() => void history.load()}>
          Couldn’t update messages. {error}
          {updatedAt ? ` Last updated ${updatedAt.toLocaleTimeString()}.` : ""}
        </Feedback>
      )}
      {history.notice && <Feedback tone="info">{history.notice}</Feedback>}
      {loading && page.messages.length === 0 ? (
        <div
          className="message-skeleton"
          role="status"
          aria-label="Loading messages"
        >
          <span>Loading your inbox…</span>
          {[0, 1, 2].map((row) => (
            <div className="skeleton-row" key={row}>
              <i />
              <i />
              <i />
            </div>
          ))}
        </div>
      ) : visible.length === 0 ? (
        <section className="empty-state">
          <Icon name="inbox" size={28} />
          <h2>
            {onlyFailed
              ? "No failed deliveries on this page"
              : error
                ? "Messages unavailable"
                : "Your inbox is ready"}
          </h2>
          <p className="muted">
            {onlyFailed
              ? "Other pages may still contain failed deliveries. Browse older history or view all messages."
              : error
                ? "Try refreshing to load your message history."
                : "Send your first message, or connect a script with your ingest token."}
          </p>
          <button
            className="secondary"
            onClick={
              onlyFailed
                ? () => setOnlyFailed(false)
                : error
                  ? () => void history.load()
                  : onCompose
            }
          >
            {onlyFailed
              ? "View all messages"
              : error
                ? "Refresh messages"
                : "Send a message"}
          </button>
        </section>
      ) : (
        <div className={`inbox-layout${detailOpen ? " has-detail" : ""}`}>
          <section className="message-list" aria-label="Message history">
            {visible.map((message) => {
              const summary = deliverySummary(message);
              return (
                <button
                  key={message.id}
                  ref={selected?.id === message.id ? selectedButton : undefined}
                  className="message-row"
                  aria-pressed={selected?.id === message.id}
                  onClick={() => {
                    listScroll.current = window.scrollY;
                    onSelect(message.id);
                    setDetailOpen(true);
                    if (window.matchMedia("(max-width: 1100px)").matches)
                      window.scrollTo({ top: 0 });
                  }}
                >
                  <span className="message-row-heading">
                    <strong>{message.title || "Untitled message"}</strong>
                    <Icon name="arrow" size={16} />
                  </span>
                  <span className="message-excerpt">{message.body}</span>
                  <span className="message-row-meta">
                    <time dateTime={message.received_at}>
                      {dateTime(message.received_at)}
                    </time>
                    <span>Priority {message.priority}</span>
                  </span>
                  <span className="message-row-result">
                    <span className={`status ${summary.tone}`}>
                      {summary.label}
                    </span>
                    <span>
                      {summary.sent} of {summary.total} delivered
                    </span>
                  </span>
                </button>
              );
            })}
          </section>
          {selected && (
            <MessageDetail
              message={selected}
              opened={detailOpen}
              onBack={back}
              retrying={history.retrying}
              onRetry={(id) => void history.retry(id)}
            />
          )}
        </div>
      )}
      <div className="pagination">
        <button
          className="secondary"
          disabled={!history.before || loading}
          onClick={() => {
            history.latest();
            setDetailOpen(false);
          }}
        >
          <Icon name="back" />
          Latest messages
        </button>
        <span className="small muted">Up to 50 per page</span>
        <button
          className="secondary"
          disabled={!page.next_cursor || loading}
          onClick={() => {
            history.older();
            setDetailOpen(false);
            window.scrollTo({ top: 0 });
          }}
        >
          Older messages
          <Icon name="arrow" />
        </button>
      </div>
    </main>
  );
}
