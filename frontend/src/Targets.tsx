import { useState } from "react";
import { api } from "./lib/api";
import type { Config, Kind, Target, TargetInput } from "./lib/types";

type Props = {
  token: string;
  targets: Target[];
  reload: () => Promise<void>;
  report: (error: unknown) => void;
};
const newTarget = (): TargetInput => ({
  name: "",
  kind: "bark",
  config: {},
  enabled: true,
  is_default: false,
});

export function Targets({ token, targets, reload, report }: Props) {
  const [editing, setEditing] = useState<Target | null>(null);
  const [draft, setDraft] = useState<TargetInput>(newTarget);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const field = (name: string, value: string | number | boolean) =>
    setDraft((previous) => ({
      ...previous,
      config: { ...previous.config, [name]: value },
    }));
  const reset = () => {
    setEditing(null);
    setDraft(newTarget());
  };
  const textField = (
    name: string,
    label: string,
    options: {
      secret?: boolean;
      required?: boolean;
      placeholder?: string;
    } = {},
  ) => (
    <label>
      {label}
      {options.secret && editing ? " (blank keeps existing)" : ""}
      <input
        type={options.secret ? "password" : "text"}
        autoComplete="off"
        value={String(draft.config[name] ?? "")}
        onChange={(event) => field(name, event.target.value)}
        required={options.required && !(options.secret && editing)}
        placeholder={options.placeholder}
      />
    </label>
  );

  return (
    <main className="stack">
      <section className="panel">
        <h2>{editing ? `Edit ${editing.name}` : "Add a delivery target"}</h2>
        <p className="muted">
          Credentials are encrypted on the server and never returned to the
          dashboard.
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setNotice("");
            const config: Config = { ...draft.config };
            for (const key of [
              "device_key",
              "access_token",
              "app_token",
              "password",
            ]) {
              if (!config[key]) delete config[key];
            }
            if (draft.kind === "mqtt") {
              config.broker_port = Number(config.broker_port ?? 1883);
              config.qos = Number(config.qos ?? 1);
            }
            try {
              await api<Target>(
                token,
                editing ? `/targets/${editing.id}` : "/targets",
                {
                  method: editing ? "PUT" : "POST",
                  body: JSON.stringify({ ...draft, config }),
                },
              );
              await reload();
              setNotice(editing ? "Target updated." : "Target created.");
              reset();
            } catch (error) {
              report(error);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="columns">
            <label>
              Name
              <input
                value={draft.name}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    name: event.target.value,
                  }))
                }
                required
                maxLength={200}
              />
            </label>
            <label>
              Provider
              <select
                aria-label="Provider"
                disabled={Boolean(editing)}
                value={draft.kind}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    kind: event.target.value as Kind,
                    config: {},
                  }))
                }
              >
                <option value="bark">Bark</option>
                <option value="ntfy">ntfy</option>
                <option value="mqtt">MQTT</option>
                <option value="gotify">Gotify</option>
              </select>
            </label>
          </div>
          {draft.kind !== "mqtt" &&
            textField("server_base_url", "Server URL", {
              required: true,
              placeholder: "https://notify.example.com",
            })}
          {draft.kind === "bark" &&
            textField("device_key", "Device key", {
              secret: true,
              required: true,
            })}
          {draft.kind === "ntfy" && (
            <>
              {textField("topic", "Topic", { required: true })}
              {textField("access_token", "Access token (optional)", {
                secret: true,
              })}
            </>
          )}
          {draft.kind === "gotify" &&
            textField("app_token", "Application token", {
              secret: true,
              required: true,
            })}
          {draft.kind === "mqtt" && (
            <>
              <div className="columns">
                {textField("broker_host", "Broker host", { required: true })}
                <label>
                  Broker port
                  <input
                    type="number"
                    min={1}
                    max={65535}
                    value={Number(draft.config.broker_port ?? 1883)}
                    onChange={(event) =>
                      field("broker_port", Number(event.target.value))
                    }
                    required
                  />
                </label>
              </div>
              {textField("topic", "Publish topic", { required: true })}
              <div className="columns">
                {textField("username", "Username (optional)")}
                {textField("password", "Password", {
                  secret: true,
                  required: Boolean(draft.config.username),
                })}
              </div>
              <div className="columns">
                <label>
                  Quality of service
                  <select
                    aria-label="Quality of service"
                    value={Number(draft.config.qos ?? 1)}
                    onChange={(event) =>
                      field("qos", Number(event.target.value))
                    }
                  >
                    <option value={0}>0</option>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                  </select>
                </label>
                <div className="choices">
                  <label className="inline">
                    <input
                      type="checkbox"
                      checked={Boolean(draft.config.tls)}
                      onChange={(event) => field("tls", event.target.checked)}
                    />
                    TLS
                  </label>
                  <label className="inline">
                    <input
                      type="checkbox"
                      checked={Boolean(draft.config.retain)}
                      onChange={(event) =>
                        field("retain", event.target.checked)
                      }
                    />
                    Retain
                  </label>
                </div>
              </div>
            </>
          )}
          <div className="choices">
            <label className="inline">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    enabled: event.target.checked,
                  }))
                }
              />
              Enabled
            </label>
            <label className="inline">
              <input
                type="checkbox"
                checked={draft.is_default}
                onChange={(event) =>
                  setDraft((previous) => ({
                    ...previous,
                    is_default: event.target.checked,
                  }))
                }
              />
              Default target
            </label>
          </div>
          <small>
            Messages without explicit targets go to all enabled default targets.
          </small>
          <div className="actions">
            <button disabled={busy}>
              {busy ? "Saving…" : editing ? "Save target" : "Add target"}
            </button>
            {editing && (
              <button type="button" className="secondary" onClick={reset}>
                Cancel edit
              </button>
            )}
          </div>
        </form>
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
      </section>
      <section className="stack" aria-label="Delivery targets">
        <h2>Targets</h2>
        {targets.length === 0 ? (
          <p className="panel">
            No targets yet. Add one and mark it as a default, or choose it
            explicitly when sending.
          </p>
        ) : (
          targets.map((target) => (
            <article key={target.id} className="panel">
              <div className="section-heading">
                <h3>{target.name}</h3>
                <span>
                  {target.kind} · {target.enabled ? "Enabled" : "Disabled"}
                  {target.is_default ? " · Default" : ""}
                </span>
              </div>
              <p className="muted">
                {String(
                  target.config.server_base_url ??
                    target.config.broker_host ??
                    "",
                )}{" "}
                · {String(target.config.topic ?? "")}
              </p>
              <small className="identifier">Target ID: {target.id}</small>
              <div className="actions">
                <button
                  className="secondary"
                  onClick={() => {
                    setEditing(target);
                    setDraft({
                      name: target.name,
                      kind: target.kind,
                      config: { ...target.config },
                      enabled: target.enabled,
                      is_default: target.is_default,
                    });
                    setNotice("");
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  Edit
                </button>
                <button
                  className="danger secondary"
                  onClick={async () => {
                    if (
                      !window.confirm(
                        `Delete target “${target.name}”? Pending deliveries must be resolved first.`,
                      )
                    )
                      return;
                    try {
                      await api(token, `/targets/${target.id}`, {
                        method: "DELETE",
                      });
                      if (editing?.id === target.id) reset();
                      await reload();
                    } catch (error) {
                      report(error);
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))
        )}
      </section>
    </main>
  );
}
