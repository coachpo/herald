import { useState } from "react";
import type { Settings } from "./lib/types";
import { api, errorText } from "./lib/api";
import { Feedback } from "./components/Feedback";
import { Modal } from "./components/Modal";
import { Icon } from "./components/Icon";

interface ConnectionProps {
  readonly token: string;
  readonly settings: Settings | null;
  readonly onCleanup: () => void;
  readonly onDisconnect: () => void;
  readonly report: (error: unknown) => void;
}

export function Connection({
  token,
  settings,
  onCleanup,
  onDisconnect,
  report,
}: ConnectionProps) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const cleanup = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ deleted: number }>(token, "/cleanup", {
        method: "POST",
      });
      setNotice(
        `Removed ${result.deleted} fully delivered message${result.deleted === 1 ? "" : "s"}. Unfinished and failed deliveries were kept.`,
      );
      setConfirm(false);
      onCleanup();
    } catch (failure) {
      setError(errorText(failure));
      report(failure);
    } finally {
      setBusy(false);
    }
  };
  return (
    <main id="main-content" className="connection-page">
      <div className="page-heading">
        <div>
          <h1 tabIndex={-1}>Connection</h1>
          <p className="muted">
            Ingest from your scripts. Keep control of your history.
          </p>
        </div>
      </div>
      <section className="settings-section">
        <div>
          <h2>Receive from your scripts</h2>
          <p className="muted">
            Use the separate ingest token from your server’s private{" "}
            <code>credentials.env</code> file.
          </p>
        </div>
        <div className="settings-content">
          {!settings ? (
            <p role="status" className="muted">
              Connection settings are not available yet.
            </p>
          ) : (
            <>
              <p>
                POST JSON to <code>{settings.ingest_path}</code> with{" "}
                <code>Authorization: Bearer $HERALD_INGEST_TOKEN</code>.
              </p>
              <pre>{`curl -X POST "${window.location.origin}${settings.ingest_path}" \\\n  -H "Authorization: Bearer $HERALD_INGEST_TOKEN" \\\n  -H 'Content-Type: application/json' \\\n  -d '{"body":"Hello from my script"}'`}</pre>
              <p className="small muted">
                Omit <code>target_ids</code> to use all enabled default targets,
                or include an array of target IDs. A successful receipt confirms
                storage; forwarding is asynchronous.
              </p>
            </>
          )}
        </div>
      </section>
      <section className="settings-section">
        <div>
          <h2>Delivered history</h2>
          <p className="muted">
            Remove old successful history without losing unfinished work.
          </p>
        </div>
        <div className="settings-content">
          <p>
            {settings
              ? `Only messages with all deliveries completed more than ${settings.retention_days} days ago are removed. Pending, retrying and failed deliveries are always kept.`
              : "Load connection settings to see the configured retention period."}
          </p>
          <button
            className="secondary danger"
            disabled={!settings || busy}
            onClick={() => {
              setConfirm(true);
              setError("");
            }}
          >
            <Icon name="clock" />
            Clean up delivered history
          </button>
          {notice && <Feedback tone="success">{notice}</Feedback>}
        </div>
      </section>
      <section className="settings-section">
        <div>
          <h2>Management session</h2>
          <p className="muted">
            This tab is connected with your management token.
          </p>
        </div>
        <div className="settings-content">
          <p>
            Disconnecting clears the token from this tab. Herald continues
            delivering queued messages on the server.
          </p>
          <button className="secondary" onClick={onDisconnect}>
            <Icon name="logout" />
            Disconnect
          </button>
        </div>
      </section>
      {confirm && (
        <Modal
          title="Clean up delivered history?"
          busy={busy}
          onClose={() => setConfirm(false)}
        >
          <p>
            Remove fully delivered messages whose deliveries completed more than{" "}
            {settings?.retention_days} days ago? This cannot be undone.
            Unfinished and failed deliveries will not be removed.
          </p>
          {error && (
            <Feedback tone="error">Couldn’t clean up history. {error}</Feedback>
          )}
          <div className="form-actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Cancel
            </button>
            <button disabled={busy} onClick={() => void cleanup()}>
              {busy ? "Cleaning up…" : "Clean up history"}
            </button>
          </div>
        </Modal>
      )}
    </main>
  );
}
