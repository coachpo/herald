import { Feedback } from "./components/Feedback";
import { Icon } from "./components/Icon";
import { Modal } from "./components/Modal";
import { TargetForm } from "./components/TargetForm";
import { RoutingRules } from "./components/RoutingRules";
import { useTargets } from "./hooks/useTargets";
import type { RoutingManager } from "./hooks/useRouting";
import type { Target } from "./lib/types";

export interface TargetsProps {
  readonly routing: RoutingManager;
  readonly token: string;
  readonly targets: readonly Target[];
  readonly reload: () => Promise<void>;
  readonly report: (error: unknown) => void;
  readonly loading?: boolean;
  readonly onRefresh?: () => void;
}

const providerNames = {
  bark: "Bark",
  ntfy: "ntfy",
  mqtt: "MQTT",
  gotify: "Gotify",
};

export function Targets({
  routing,
  token,
  targets,
  reload,
  report,
  loading = false,
  onRefresh,
}: TargetsProps) {
  const manager = useTargets({ token, reload, report });
  const locked = manager.busy !== null || manager.needsRefresh || loading;

  return (
    <main id="main-content" className="stack">
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>Delivery targets</h1>
          <p className="muted">Choose where your notifications go.</p>
        </div>
        <div className="heading-actions">
          <button
            type="button"
            className="button secondary"
            disabled={manager.busy !== null || loading}
            onClick={() => {
              if (onRefresh && !manager.needsRefresh) onRefresh();
              else void manager.refresh();
            }}
          >
            <Icon name="refresh" size={16} />
            {manager.busy === "refresh" || loading ? "Refreshing…" : "Refresh"}
          </button>
          <button
            type="button"
            className="button"
            disabled={locked}
            onClick={manager.create}
          >
            <Icon name="plus" size={16} /> Add target
          </button>
        </div>
      </div>

      {manager.notice && <Feedback tone="success">{manager.notice}</Feedback>}
      {manager.listError && (
        <Feedback tone="error" onRetry={() => void manager.refresh()}>
          {manager.listError}
        </Feedback>
      )}

      <section
        className="panel target-list"
        aria-label="Delivery targets"
        aria-busy={loading || manager.busy === "refresh"}
      >
        {loading && targets.length === 0 ? (
          <div className="empty-state" role="status">
            <p>Loading delivery targets…</p>
          </div>
        ) : targets.length === 0 ? (
          <div className="empty-state">
            <Icon name="target" size={28} />
            <h2>No destinations yet</h2>
            <p className="muted">
              Add a delivery target, then select it in routing rules, make it a
              fallback default, or choose it when sending.
            </p>
            <button
              type="button"
              className="button"
              disabled={locked}
              onClick={manager.create}
            >
              Add your first target
            </button>
          </div>
        ) : (
          targets.map((target) => (
            <article className="target-row" key={target.id}>
              <div className="target-identity">
                <h2>{target.name}</h2>
                <p className="muted small">{providerNames[target.kind]}</p>
                <span className="identifier small">{target.id}</span>
              </div>
              <div className="target-endpoint">
                <p className="identifier">
                  {String(
                    target.config.server_base_url ??
                      target.config.broker_host ??
                      "",
                  )}
                  {target.kind === "mqtt"
                    ? `:${target.config.broker_port ?? 1883}`
                    : ""}
                </p>
                {target.config.topic && (
                  <p className="muted small">
                    Topic:{" "}
                    <span className="identifier">
                      {String(target.config.topic)}
                    </span>
                  </p>
                )}
              </div>
              <div className="target-routing">
                <span
                  className={`status ${target.enabled ? "sent" : "neutral"}`}
                >
                  {target.enabled ? "Enabled" : "Disabled"}
                </span>
                {target.is_default && <span className="tag">Default</span>}
              </div>
              <div className="target-actions">
                <button
                  type="button"
                  className="button ghost"
                  disabled={locked}
                  onClick={() => manager.edit(target)}
                  aria-label={`Edit ${target.name}`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="button ghost"
                  disabled={locked}
                  onClick={() => void manager.toggle(target)}
                  aria-label={`${target.enabled ? "Disable" : "Enable"} ${target.name}`}
                >
                  {manager.busy === `toggle:${target.id}`
                    ? "Saving…"
                    : target.enabled
                      ? "Disable"
                      : "Enable"}
                </button>
                <button
                  type="button"
                  className="button ghost danger"
                  disabled={locked}
                  onClick={() => manager.confirmDelete(target)}
                  aria-label={`Delete ${target.name}`}
                >
                  Delete
                </button>
              </div>
            </article>
          ))
        )}
      </section>

      <p className="muted small">
        Enabled default targets receive automatically routed messages only when
        no routing rule matches. Disabling a target does not cancel deliveries
        already queued.
      </p>

      <RoutingRules manager={routing} targets={targets} targetsLoading={loading} />

      {manager.editor && (
        <Modal
          title={manager.editor.target ? "Edit target" : "Add delivery target"}
          onClose={manager.closeEditor}
          busy={manager.busy === "save"}
        >
          <TargetForm
            target={manager.editor.target}
            busy={manager.busy === "save"}
            error={manager.formError}
            onSubmit={manager.save}
            onCancel={manager.closeEditor}
          />
        </Modal>
      )}

      {manager.deleting && (
        <Modal
          title="Delete delivery target?"
          onClose={manager.closeDelete}
          busy={manager.busy === "delete"}
        >
          <div className="stack">
            <p>
              Delete <strong>{manager.deleting.name}</strong>? This cannot be
              undone.
            </p>
            <p className="muted">
              Remove this target from every routing rule, including disabled
              rules, and save the rules first. Targets with unfinished or failed
              deliveries cannot be deleted. Successful delivery history is kept.
            </p>
            {manager.deleteError && (
              <Feedback tone="error">{manager.deleteError}</Feedback>
            )}
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                disabled={manager.busy === "delete"}
                onClick={manager.closeDelete}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button danger"
                disabled={manager.busy === "delete"}
                onClick={() => void manager.remove()}
              >
                {manager.busy === "delete" ? "Deleting…" : "Delete target"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </main>
  );
}
