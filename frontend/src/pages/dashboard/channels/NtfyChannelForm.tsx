import { parseOptionalJsonObject } from "@/lib/json";

export interface NtfyChannelFormProps {
  canCreate: boolean;
  submitting: boolean;
  serverBaseUrl: string;
  setServerBaseUrl: (val: string) => void;
  topic: string;
  setTopic: (val: string) => void;
  authMode: "none" | "bearer" | "basic";
  setAuthMode: (val: "none" | "bearer" | "basic") => void;
  accessToken: string;
  setAccessToken: (val: string) => void;
  username: string;
  setUsername: (val: string) => void;
  password: string;
  setPassword: (val: string) => void;
  defaultHeadersJson: string;
  setDefaultHeadersJson: (val: string) => void;
}

export function NtfyChannelForm({
  canCreate,
  submitting,
  serverBaseUrl,
  setServerBaseUrl,
  topic,
  setTopic,
  authMode,
  setAuthMode,
  accessToken,
  setAccessToken,
  username,
  setUsername,
  password,
  setPassword,
  defaultHeadersJson,
  setDefaultHeadersJson,
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
          value={serverBaseUrl}
          onChange={(e) => setServerBaseUrl(e.target.value)}
          disabled={!canCreate || submitting}
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
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Auth</div>
        <select
          id="ntfy-auth-mode"
          name="auth_mode"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={authMode}
          onChange={(e) => setAuthMode(e.target.value as "none" | "bearer" | "basic")}
          disabled={!canCreate || submitting}
        >
          <option value="none">None</option>
          <option value="bearer">Bearer token</option>
          <option value="basic">Basic (user/pass)</option>
        </select>
      </label>

      {authMode === "bearer" && (
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Access token</div>
          <input
            id="ntfy-access-token"
            name="access_token"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            disabled={!canCreate || submitting}
          />
        </label>
      )}

      {authMode === "basic" && (
        <>
          <label className="block">
            <div className="text-xs font-medium text-muted-foreground">Username</div>
            <input
              id="ntfy-username"
              name="username"
              autoComplete="off"
              className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={!canCreate || submitting}
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={!canCreate || submitting}
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
          value={defaultHeadersJson}
          onChange={(e) => setDefaultHeadersJson(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>
    </>
  );
}

export function validateNtfyConfig(state: Omit<NtfyChannelFormProps, "canCreate" | "submitting" | "setServerBaseUrl" | "setTopic" | "setAuthMode" | "setAccessToken" | "setUsername" | "setPassword" | "setDefaultHeadersJson">): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
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
