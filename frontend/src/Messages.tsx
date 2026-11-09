import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api";
import type { MessagePage, Settings, Target } from "./lib/types";

type Props = {
  token: string;
  targets: Target[];
  settings: Settings | null;
  report: (error: unknown) => void;
};
const date = (value: string | null) =>
  value ? new Date(value).toLocaleString() : "—";

export function Messages({ token, targets, settings, report }: Props) {
  const [page, setPage] = useState<MessagePage>({ messages: [] });
  const [before, setBefore] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState(3);
  const [selected, setSelected] = useState<string[]>([]);
  const [explicit, setExplicit] = useState(false);
  const [onlyFailed, setOnlyFailed] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = useCallback(async () => {
    const query = new URLSearchParams({ limit: "50" });
    if (before) query.set("before", before);
    setPage(await api<MessagePage>(token, `/messages?${query}`));
  }, [token, before]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const refresh = () => {
      void load()
        .catch((error) => {
          if (active) report(error);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [load, report]);

  const enabled = targets.filter((target) => target.enabled);
  const defaults = enabled.filter((target) => target.is_default);
  const visible = onlyFailed
    ? page.messages.filter((message) =>
        message.deliveries.some((delivery) => delivery.status === "failed"),
      )
    : page.messages;

  return (
    <main className="stack">
      <section className="panel">
        <h2>Send a message</h2>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setNotice("");
            try {
              const result = await api<{
                message_id: string;
                duplicate: boolean;
              }>(token, "/messages", {
                method: "POST",
                body: JSON.stringify({
                  title,
                  body,
                  priority,
                  ...(explicit ? { target_ids: selected } : {}),
                }),
              });
              setNotice(
                `Message stored and queued: ${result.message_id}. Delivery results appear below.`,
              );
              setBody("");
              setTitle("");
              setBefore(undefined);
              if (!before) await load();
            } catch (error) {
              report(error);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="columns">
            <label>
              Title
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label>
              Priority
              <select
                aria-label="Priority"
                value={priority}
                onChange={(event) => setPriority(Number(event.target.value))}
              >
                {[1, 2, 3, 4, 5].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Message
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={3}
              required
            />
          </label>
          <fieldset>
            <legend>Delivery targets</legend>
            <label className="inline">
              <input
                type="checkbox"
                checked={explicit}
                onChange={(event) => setExplicit(event.target.checked)}
              />
              Choose specific targets
            </label>
            {explicit ? (
              <div className="choices">
                {enabled.map((target) => (
                  <label key={target.id} className="inline">
                    <input
                      type="checkbox"
                      checked={selected.includes(target.id)}
                      onChange={(event) =>
                        setSelected((previous) =>
                          event.target.checked
                            ? [...previous, target.id]
                            : previous.filter((id) => id !== target.id),
                        )
                      }
                    />
                    {target.name}
                  </label>
                ))}
                {enabled.length === 0 && <p>Add an enabled target first.</p>}
              </div>
            ) : (
              <p className="muted">
                Default targets:{" "}
                {defaults.map((target) => target.name).join(", ") ||
                  "None. Configure a default target or choose specific targets."}
              </p>
            )}
          </fieldset>
          <button
            disabled={
              busy ||
              !body.trim() ||
              (explicit ? selected.length === 0 : defaults.length === 0)
            }
          >
            {busy ? "Storing…" : "Store and queue"}
          </button>
        </form>
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
      </section>

      <section className="panel receive">
        <h2>Receive from your scripts</h2>
        <p>
          POST JSON to <code>{settings?.ingest_path ?? "/api/ingest"}</code>{" "}
          with <code>Authorization: Bearer $HERALD_INGEST_TOKEN</code>. Read
          this separate token from the server’s private{" "}
          <code>credentials.env</code> file.
        </p>
        <pre>{`curl -X POST "${window.location.origin}${settings?.ingest_path ?? "/api/ingest"}" \\\n  -H "Authorization: Bearer $HERALD_INGEST_TOKEN" \\\n  -H 'Content-Type: application/json' \\\n  -d '{"body":"Hello from my script"}'`}</pre>
        <small>
          Omit target_ids to use enabled default targets, or include an array of
          target IDs. A successful receipt means the message is stored;
          forwarding happens asynchronously.
        </small>
      </section>

      <section className="stack" aria-label="Message history">
        <div className="section-heading">
          <div>
            <h2>Messages & delivery results</h2>
            <p className="muted">
              Updates every 4 seconds. Failed deliveries stay available for
              manual retry.
            </p>
          </div>
          <button
            className="secondary"
            onClick={() => void load().catch(report)}
          >
            Refresh
          </button>
        </div>
        <div className="toolbar">
          <label className="inline">
            <input
              type="checkbox"
              checked={onlyFailed}
              onChange={(event) => setOnlyFailed(event.target.checked)}
            />
            Failed deliveries on this page
          </label>
          <button
            className="secondary"
            onClick={async () => {
              try {
                const result = await api<{ deleted: number }>(
                  token,
                  "/cleanup",
                  { method: "POST" },
                );
                setNotice(
                  `Removed ${result.deleted} fully delivered messages older than ${settings?.retention_days ?? 30} days.`,
                );
                await load();
              } catch (error) {
                report(error);
              }
            }}
          >
            Clean up delivered history
          </button>
        </div>
        {loading ? (
          <p role="status">Loading messages…</p>
        ) : visible.length === 0 ? (
          <p className="panel">
            {onlyFailed
              ? "No failed deliveries on this page."
              : "No messages yet."}
          </p>
        ) : (
          visible.map((message) => (
            <article className="panel message" key={message.id}>
              <div className="section-heading">
                <h3>{message.title || "Untitled message"}</h3>
                <span className="muted">
                  Priority {message.priority} · {date(message.received_at)}
                </span>
              </div>
              <p className="message-body">{message.body}</p>
              <small className="identifier">{message.id}</small>
              <div className="deliveries">
                {message.deliveries.map((delivery) => (
                  <div className="delivery" key={delivery.id}>
                    <div className="section-heading">
                      <strong>{delivery.target_name}</strong>
                      <span className={`status ${delivery.status}`}>
                        {delivery.status}
                      </span>
                    </div>
                    <p className="muted">
                      {delivery.attempts} attempt
                      {delivery.attempts === 1 ? "" : "s"}
                      {delivery.completed_at
                        ? ` · Completed ${date(delivery.completed_at)}`
                        : delivery.available_at && delivery.status === "retry"
                          ? ` · Next attempt ${date(delivery.available_at)}`
                          : ""}
                    </p>
                    {delivery.last_error && (
                      <p className="error">{delivery.last_error}</p>
                    )}
                    {delivery.status === "failed" && (
                      <button
                        disabled={retrying === delivery.id}
                        className="secondary"
                        onClick={async () => {
                          setRetrying(delivery.id);
                          try {
                            await api(
                              token,
                              `/deliveries/${delivery.id}/retry`,
                              { method: "POST" },
                            );
                            setNotice(
                              "Failed delivery queued for another attempt. Check its result below.",
                            );
                            await load();
                          } catch (error) {
                            report(error);
                          } finally {
                            setRetrying(null);
                          }
                        }}
                      >
                        {retrying === delivery.id
                          ? "Queuing…"
                          : "Retry failed delivery"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </article>
          ))
        )}
        <div className="toolbar">
          <button
            className="secondary"
            disabled={!before}
            onClick={() => setBefore(undefined)}
          >
            Latest messages
          </button>
          <button
            className="secondary"
            disabled={!page.next_cursor || loading}
            onClick={() => setBefore(page.next_cursor ?? undefined)}
          >
            Older messages
          </button>
        </div>
        <small>
          Cleanup removes only fully delivered messages older than{" "}
          {settings?.retention_days ?? 30} days. Pending and failed deliveries
          are kept.
        </small>
      </section>
    </main>
  );
}
