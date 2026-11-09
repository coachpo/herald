import { useId, useState } from "react";
import type { Kind, Target, TargetInput } from "../lib/types";
import { Feedback } from "./Feedback";

export interface TargetFormProps {
  readonly target: Target | null;
  readonly busy: boolean;
  readonly error: string;
  readonly onSubmit: (input: TargetInput) => Promise<void>;
  readonly onCancel: () => void;
}

function isKind(value: string): value is Kind {
  return (
    value === "bark" ||
    value === "ntfy" ||
    value === "mqtt" ||
    value === "gotify"
  );
}

export function TargetForm({
  target,
  busy,
  error,
  onSubmit,
  onCancel,
}: TargetFormProps) {
  const id = useId();
  const [draft, setDraft] = useState<TargetInput>(() =>
    target
      ? {
          name: target.name,
          kind: target.kind,
          config: { ...target.config },
          enabled: target.enabled,
          is_default: target.is_default,
        }
      : {
          name: "",
          kind: "bark",
          config: {},
          enabled: true,
          is_default: false,
        },
  );
  const field = (name: string, value: string | number | boolean) => {
    setDraft((previous) => ({
      ...previous,
      config: { ...previous.config, [name]: value },
    }));
  };
  const textField = (
    name: string,
    label: string,
    options: {
      secret?: boolean;
      required?: boolean;
      placeholder?: string;
      help?: string;
      pattern?: string;
      url?: boolean;
    } = {},
  ) => {
    const help =
      options.secret && target
        ? "Leave blank to keep the stored credential."
        : options.help;
    return (
      <label className="field" htmlFor={`${id}-${name}`}>
        {label}
        <input
          id={`${id}-${name}`}
          type={options.secret ? "password" : options.url ? "url" : "text"}
          autoComplete={options.secret ? "new-password" : "off"}
          value={String(draft.config[name] ?? "")}
          onChange={(event) => field(name, event.target.value)}
          required={options.required && !(options.secret && target)}
          placeholder={options.placeholder}
          pattern={options.pattern}
          aria-describedby={help ? `${id}-${name}-help` : undefined}
        />
        {help && (
          <span className="field-help" id={`${id}-${name}-help`}>
            {help}
          </span>
        )}
      </label>
    );
  };

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(draft);
      }}
      aria-busy={busy}
    >
      <p className="muted small">
        Credentials are encrypted on your server and are never returned to this
        dashboard.
      </p>
      {error && <Feedback tone="error">{error}</Feedback>}
      <fieldset className="form-section" disabled={busy}>
        <legend>Destination</legend>
        <div className="form-grid">
          <label className="field" htmlFor={`${id}-name`}>
            Target name
            <input
              id={`${id}-name`}
              value={draft.name}
              onChange={(event) =>
                setDraft((previous) => ({
                  ...previous,
                  name: event.target.value,
                }))
              }
              required
              maxLength={200}
              autoComplete="off"
              placeholder="e.g. Personal phone"
            />
          </label>
          <label className="field" htmlFor={`${id}-provider`}>
            Provider
            <select
              id={`${id}-provider`}
              value={draft.kind}
              disabled={Boolean(target)}
              onChange={(event) => {
                const kind = event.target.value;
                if (isKind(kind))
                  setDraft((previous) => ({ ...previous, kind, config: {} }));
              }}
            >
              <option value="bark">Bark</option>
              <option value="ntfy">ntfy</option>
              <option value="mqtt">MQTT</option>
              <option value="gotify">Gotify</option>
            </select>
            {target && (
              <span className="field-help">
                Provider is fixed for this target.
              </span>
            )}
          </label>
        </div>
      </fieldset>

      <fieldset className="form-section" disabled={busy}>
        <legend>
          {draft.kind === "mqtt" ? "Broker connection" : "Provider connection"}
        </legend>
        {draft.kind !== "mqtt" &&
          textField("server_base_url", "Server URL", {
            required: true,
            url: true,
          })}
        {draft.kind === "bark" &&
          textField("device_key", "Device key", {
            required: true,
            secret: true,
          })}
        {draft.kind === "ntfy" && (
          <>
            {textField("topic", "Topic", {
              required: true,
              pattern: "[A-Za-z0-9_-]+",
              help: "Letters, numbers, underscores and hyphens only.",
            })}
            {textField("access_token", "Access token (optional)", {
              secret: true,
            })}
          </>
        )}
        {draft.kind === "gotify" &&
          textField("app_token", "Application token", {
            required: true,
            secret: true,
          })}
        {draft.kind === "mqtt" && (
          <>
            <div className="form-grid">
              {textField("broker_host", "Broker host", { required: true })}
              <label className="field" htmlFor={`${id}-port`}>
                Broker port
                <input
                  id={`${id}-port`}
                  type="number"
                  min={1}
                  max={65535}
                  step={1}
                  required
                  value={String(draft.config.broker_port ?? 1883)}
                  onChange={(event) => field("broker_port", event.target.value)}
                />
                <span className="field-help">
                  Default 1883; set the port your broker uses for TLS.
                </span>
              </label>
            </div>
            {textField("topic", "Publish topic", {
              required: true,
              help: "Use a publish topic without # or + wildcards.",
            })}
            <div className="form-grid">
              {textField("username", "Username (optional)")}
              {textField("password", "Password", {
                secret: true,
                required: Boolean(draft.config.username),
                help: "Required when a username is provided.",
              })}
            </div>
            <label className="field" htmlFor={`${id}-qos`}>
              Quality of service
              <select
                id={`${id}-qos`}
                value={Number(draft.config.qos ?? 1)}
                onChange={(event) => field("qos", Number(event.target.value))}
              >
                <option value={0}>0 — At most once</option>
                <option value={1}>1 — At least once</option>
                <option value={2}>2 — Exactly once</option>
              </select>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={Boolean(draft.config.tls)}
                onChange={(event) => field("tls", event.target.checked)}
              />
              Use TLS for the broker connection
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={Boolean(draft.config.retain)}
                onChange={(event) => field("retain", event.target.checked)}
              />
              Retain the message on the broker
            </label>
          </>
        )}
      </fieldset>

      <fieldset className="form-section" disabled={busy}>
        <legend>Routing</legend>
        <label className="checkbox-row">
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
          Enabled for new messages
        </label>
        <label className="checkbox-row">
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
          Fallback default target
        </label>
        <p className="field-help">
          Automatic routing uses enabled default targets only when no rule
          matches. Existing queued deliveries are not changed.
        </p>
      </fieldset>

      <div className="form-actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : target ? "Save target" : "Create target"}
        </button>
      </div>
    </form>
  );
}
