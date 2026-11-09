import type { Target } from "./lib/types";
import { useComposer } from "./hooks/useComposer";
import { Feedback } from "./components/Feedback";
import { Icon } from "./components/Icon";

interface SendMessageProps {
  readonly token: string;
  readonly targets: Target[];
  readonly onStored: (id: string) => void;
  readonly onView: (id: string) => void;
  readonly onTargets: () => void;
  readonly report: (error: unknown) => void;
  readonly loading: boolean;
}

export function SendMessage({
  token,
  targets,
  onStored,
  onView,
  onTargets,
  report,
  loading,
}: SendMessageProps) {
  const form = useComposer(token, targets, onStored, report);
  return (
    <main id="main-content" className="compose-page">
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>Send message</h1>
          <p className="muted">Store once. Forward to your selected targets.</p>
        </div>
      </div>
      <div className="compose-layout">
        <section className="compose-form">
          {form.receipt && (
            <Feedback tone="info">
              <strong>
                {form.receipt.duplicate
                  ? "Already received"
                  : "Received and queued"}
              </strong>
              <p>Delivery continues in the background.</p>
              <code className="identifier">{form.receipt.id}</code>
              <button
                className="ghost"
                onClick={() => onView(form.receipt!.id)}
              >
                View message
                <Icon name="arrow" />
              </button>
            </Feedback>
          )}
          {form.error && (
            <Feedback tone="error">
              Couldn’t send the message. {form.error}
            </Feedback>
          )}
          <form
            onSubmit={(event) => void form.submit(event)}
            aria-busy={form.busy}
          >
            <fieldset className="form-fields" disabled={form.busy || loading}>
              <label className="field">
                Title <span className="field-help">Optional</span>
                <input
                  value={form.title}
                  onChange={(event) => form.setTitle(event.target.value)}
                />
              </label>
              <label className="field">
                Message{" "}
                <span className="field-help">Required · plain text</span>
                <textarea
                  value={form.body}
                  onChange={(event) => form.setBody(event.target.value)}
                  rows={7}
                  required
                />
              </label>
              <label className="field priority-field">
                Priority
                <select
                  value={form.priority}
                  onChange={(event) =>
                    form.setPriority(Number(event.target.value))
                  }
                  aria-label="Priority"
                >
                  <option value={1}>1 — Lowest</option>
                  <option value={2}>2 — Low</option>
                  <option value={3}>3 — Normal</option>
                  <option value={4}>4 — High</option>
                  <option value={5}>5 — Highest</option>
                </select>
              </label>
              <fieldset className="routing-fieldset">
                <legend>Delivery targets</legend>
                <div className="routing-modes">
                  <label className="checkbox-row">
                    <input
                      type="radio"
                      name="routing"
                      checked={!form.explicit}
                      onChange={() => form.setExplicit(false)}
                    />
                    Automatic · rules, then default fallback
                  </label>
                  <label className="checkbox-row">
                    <input
                      type="radio"
                      name="routing"
                      checked={form.explicit}
                      onChange={() => form.setExplicit(true)}
                    />
                    Choose specific targets
                  </label>
                </div>
                {loading ? (
                  <p role="status">Loading targets…</p>
                ) : form.explicit ? (
                  <div className="target-choices">
                    {form.enabled.map((target) => (
                      <label className="target-choice" key={target.id}>
                        <input
                          type="checkbox"
                          checked={form.selected.includes(target.id)}
                          onChange={(event) =>
                            form.setSelected((previous) =>
                              event.target.checked
                                ? [...previous, target.id]
                                : previous.filter((id) => id !== target.id),
                            )
                          }
                        />
                        <span>
                          <strong>{target.name}</strong>
                          <span className="small muted">
                            {target.kind}
                            {target.is_default ? " · Default" : ""}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="routing-help">
                    The server selects the union of all matching rules’ targets.
                    If no rule matches, it uses enabled default targets. The
                    receipt is rejected if there are no targets or any selected
                    target is unavailable. Check the stored message for the
                    actual targets and routing decision.
                  </p>
                )}
                {!loading && form.explicit && form.destinations.length === 0 && (
                  <p className="routing-help">
                    {form.enabled.length > 0
                      ? "Choose at least one target."
                      : "No enabled targets. Configure a target before selecting it."}
                  </p>
                )}
              </fieldset>
            </fieldset>
            {!loading && !form.enabled.length && (
              <Feedback>
                No enabled targets.{" "}
                <button type="button" className="ghost" onClick={onTargets}>
                  Configure targets
                  <Icon name="arrow" />
                </button>
              </Feedback>
            )}
            <div className="form-actions">
              <button
                disabled={
                  form.busy ||
                  loading ||
                  !form.body.trim() ||
                  (form.explicit && form.destinations.length === 0)
                }
              >
                <Icon name="send" />
                {form.busy ? "Storing…" : "Store and queue"}
              </button>
              <span className="small muted">
                {form.explicit
                  ? `${form.destinations.length} target${form.destinations.length === 1 ? "" : "s"} selected`
                  : "Targets selected by the server at receipt"}
              </span>
            </div>
          </form>
        </section>
        <aside className="compose-guide">
          <h2>Receipt is not delivery</h2>
          <ol>
            <li>
              <strong>Receive</strong>
              <p>
                Your message and all selected deliveries are saved together.
              </p>
            </li>
            <li>
              <strong>Queue</strong>
              <p>
                Herald forwards in the background. You can leave this screen.
              </p>
            </li>
            <li>
              <strong>Check results</strong>
              <p>
                Open the message to see each target’s result. Final failures
                stay available for manual retry.
              </p>
            </li>
          </ol>
          <p className="small muted">
            Explicit selection bypasses routing rules and default targets.
            Automatic selection uses enabled defaults only when no rule matches.
            Rules and default changes affect new receipts, not queued deliveries.
          </p>
        </aside>
      </div>
    </main>
  );
}
