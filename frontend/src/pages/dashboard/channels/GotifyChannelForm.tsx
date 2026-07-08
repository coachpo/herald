import { parseOptionalJsonObject } from "@/lib/json";
import type { GotifyFormValues } from "./formState";

export interface GotifyChannelFormProps {
  submitting: boolean;
  values: GotifyFormValues;
  onChange: (values: GotifyFormValues) => void;
}

export function GotifyChannelForm({
  submitting,
  values,
  onChange,
}: GotifyChannelFormProps) {
  return (
    <>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Server base URL</div>
        <input
          id="gotify-server-base-url"
          name="server_base_url"
          autoComplete="url"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          placeholder="https://gotify.example.com"
          value={values.serverBaseUrl}
          onChange={(e) => onChange({ ...values, serverBaseUrl: e.target.value })}
          disabled={submitting}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          Your Gotify server URL (e.g., https://gotify.example.com)
        </div>
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">App token</div>
        <input
          id="gotify-app-token"
          name="app_token"
          autoComplete="off"
          type="password"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          placeholder="Apx..."
          value={values.appToken}
          onChange={(e) => onChange({ ...values, appToken: e.target.value })}
          disabled={submitting}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          Application token from Gotify (not client token)
        </div>
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Default priority (optional)</div>
        <input
          id="gotify-default-priority"
          name="default_priority"
          type="number"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          placeholder="5"
          min={0}
          max={10}
          value={values.defaultPriority}
          onChange={(e) => onChange({ ...values, defaultPriority: e.target.value })}
          disabled={submitting}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          0 (min) to 10 (urgent). Leave empty to use message priority.
        </div>
      </label>
      <label className="block md:col-span-2">
        <div className="text-xs font-medium text-muted-foreground">Default extras JSON (optional)</div>
        <textarea
          id="gotify-default-extras-json"
          name="default_extras_json"
          className="mt-1 h-24 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 font-mono text-xs"
          placeholder='{"client::display": {"contentType": "text/markdown"}}'
          value={values.defaultExtrasJson}
          onChange={(e) => onChange({ ...values, defaultExtrasJson: e.target.value })}
          disabled={submitting}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          JSON object for markdown, click URLs, etc.
        </div>
      </label>
    </>
  );
}

export function validateGotifyConfig(state: GotifyFormValues): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  const baseUrl = state.serverBaseUrl.trim();
  const token = state.appToken.trim();
  if (!baseUrl) {
    return { ok: false, error: "Server base URL is required." };
  }
  if (!token) {
    return { ok: false, error: "App token is required." };
  }
  const cfg: Record<string, unknown> = { server_base_url: baseUrl, app_token: token };
  const priorityNum = parseInt(state.defaultPriority.trim(), 10);
  if (!isNaN(priorityNum)) {
    if (priorityNum < 0 || priorityNum > 10) {
      return { ok: false, error: "Priority must be between 0 and 10." };
    }
    cfg.default_priority = priorityNum;
  }
  const extrasResult = parseOptionalJsonObject(state.defaultExtrasJson);
  if (!extrasResult.ok) {
    return { ok: false, error: `Default extras JSON: ${extrasResult.error}` };
  }
  if (Object.keys(extrasResult.value).length > 0) {
    cfg.default_extras_json = extrasResult.value;
  }
  return { ok: true, config: cfg };
}
