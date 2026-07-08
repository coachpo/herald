import { parseOptionalJsonObject } from "@/lib/json";
import type { NtfyFormValues } from "./formState";

export interface NtfyChannelFormProps {
  submitting: boolean;
  values: NtfyFormValues;
  onChange: (values: NtfyFormValues) => void;
}

export function NtfyChannelForm({
  submitting,
  values,
  onChange,
}: NtfyChannelFormProps) {
  return (
    <>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Server base URL</div>
        <input
          id="ntfy-server-base-url"
          name="server_base_url"
          autoComplete="url"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          placeholder="https://ntfy.sh"
          value={values.serverBaseUrl}
          onChange={(e) => onChange({ ...values, serverBaseUrl: e.target.value })}
          disabled={submitting}
        />
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Topic</div>
        <input
          id="ntfy-topic"
          name="topic"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          placeholder="mytopic"
          value={values.topic}
          onChange={(e) => onChange({ ...values, topic: e.target.value })}
          disabled={submitting}
        />
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Auth</div>
        <select
          id="ntfy-auth-mode"
          name="auth_mode"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={values.authMode}
          onChange={(e) => onChange({ ...values, authMode: e.target.value as "none" | "bearer" | "basic" })}
          disabled={submitting}
        >
          <option value="none">None</option>
          <option value="bearer">Bearer token</option>
          <option value="basic">Basic (user/pass)</option>
        </select>
      </label>

      {values.authMode === "bearer" && (
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Access token</div>
          <input
            id="ntfy-access-token"
            name="access_token"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
            value={values.accessToken}
            onChange={(e) => onChange({ ...values, accessToken: e.target.value })}
            disabled={submitting}
          />
        </label>
      )}

      {values.authMode === "basic" && (
        <>
          <label className="block">
            <div className="text-xs font-medium text-muted-foreground">Username</div>
            <input
              id="ntfy-username"
              name="username"
              autoComplete="off"
              className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
              value={values.username}
              onChange={(e) => onChange({ ...values, username: e.target.value })}
              disabled={submitting}
            />
          </label>
          <label className="block">
            <div className="text-xs font-medium text-muted-foreground">Password</div>
            <input
              id="ntfy-password"
              name="password"
              autoComplete="off"
              className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
              type="password"
              value={values.password}
              onChange={(e) => onChange({ ...values, password: e.target.value })}
              disabled={submitting}
            />
          </label>
        </>
      )}

      <label className="block md:col-span-2">
        <div className="text-xs font-medium text-muted-foreground">Default headers JSON</div>
        <textarea
          id="ntfy-default-headers-json"
          name="default_headers_json"
          className="mt-1 h-24 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 font-mono text-xs"
          value={values.defaultHeadersJson}
          onChange={(e) => onChange({ ...values, defaultHeadersJson: e.target.value })}
          disabled={submitting}
        />
      </label>
    </>
  );
}

export function validateNtfyConfig(state: NtfyFormValues): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  if (!state.serverBaseUrl.trim()) {
    return { ok: false, error: "Server base URL is required." };
  }
  if (!state.topic.trim()) {
    return { ok: false, error: "Topic is required." };
  }
  const parsed = parseOptionalJsonObject(state.defaultHeadersJson);
  if (!parsed.ok) {
    return { ok: false, error: `Default headers JSON: ${parsed.error}` };
  }
  const token = state.accessToken.trim();
  const user = state.username.trim();
  const pass = state.password;
  if (state.authMode === "bearer" && !token) {
    return { ok: false, error: "Access token is required for bearer auth." };
  }
  if (state.authMode === "basic" && (!user.trim() || !pass.trim())) {
    return { ok: false, error: "Username and password are required for basic auth." };
  }
  return {
    ok: true,
    config: {
      server_base_url: state.serverBaseUrl.trim(),
      topic: state.topic.trim(),
      access_token: state.authMode === "bearer" ? token : undefined,
      username: state.authMode === "basic" ? user : undefined,
      password: state.authMode === "basic" ? pass : undefined,
      default_headers_json: parsed.value,
    },
  };
}
