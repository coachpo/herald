import { parseOptionalJsonObject } from "@/lib/json";

function looksLikeBarkDeviceKey(seg: string): boolean {
  const s = (seg || "").trim();
  if (s.length < 16) return false;
  if (!/^[A-Za-z0-9_-]+$/.test(s)) return false;
  return /\d/.test(s);
}

function trySplitBarkUrl(input: string): { serverBaseUrl: string; deviceKey: string } | null {
  const raw = (input || "").trim();
  if (!raw) return null;
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return null;
  }

  const path = u.pathname.replace(/\/+$/, "");
  if (path === "" || path === "/") {
    return null;
  }

  if (path === "/push") {
    return null;
  }

  const segs = path.split("/").filter(Boolean);
  if (segs.length !== 1) return null;
  const seg = segs[0];
  if (!looksLikeBarkDeviceKey(seg)) return null;
  return { serverBaseUrl: u.origin, deviceKey: seg };
}

export interface BarkChannelFormProps {
  canCreate: boolean;
  submitting: boolean;
  serverBaseUrl: string;
  setServerBaseUrl: (val: string) => void;
  deviceKey: string;
  setDeviceKey: (val: string) => void;
  useDeviceKeys: boolean;
  setUseDeviceKeys: (val: boolean) => void;
  deviceKeysText: string;
  setDeviceKeysText: (val: string) => void;
  defaultPayloadJson: string;
  setDefaultPayloadJson: (val: string) => void;
}

export function BarkChannelForm({
  canCreate,
  submitting,
  serverBaseUrl,
  setServerBaseUrl,
  deviceKey,
  setDeviceKey,
  useDeviceKeys,
  setUseDeviceKeys,
  deviceKeysText,
  setDeviceKeysText,
  defaultPayloadJson,
  setDefaultPayloadJson,
}: BarkChannelFormProps) {
  return (
    <>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Server base URL</div>
        <input
          id="bark-server-base-url"
          name="server_base_url"
          autoComplete="url"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          placeholder="https://bark.example.com (or paste https://bark.example.com/<device_key>/)"
          value={serverBaseUrl}
          onChange={(e) => setServerBaseUrl(e.target.value)}
          onBlur={(e) => {
            const split = trySplitBarkUrl(e.target.value);
            if (!split) return;
            setServerBaseUrl(split.serverBaseUrl);
            if (useDeviceKeys) {
              if (!deviceKeysText.trim()) {
                setDeviceKeysText(split.deviceKey);
              }
            } else {
              if (!deviceKey.trim()) setDeviceKey(split.deviceKey);
            }
          }}
          disabled={!canCreate || submitting}
        />
      </label>
      <label className="flex items-end gap-2">
        <input
          id="bark-multiple-devices"
          name="multiple_devices"
          type="checkbox"
          checked={useDeviceKeys}
          onChange={(e) => {
            const on = e.target.checked;
            setUseDeviceKeys(on);
            if (!on) {
              setDeviceKeysText("");
            }
          }}
          disabled={!canCreate || submitting}
        />
        <span className="text-sm text-muted-foreground">Multiple devices</span>
      </label>
      {useDeviceKeys ? (
        <label className="block md:col-span-2">
          <div className="text-xs font-medium text-muted-foreground">Device keys</div>
          <div className="mt-1 text-[10px] text-muted-foreground">One per line</div>
          <textarea
            id="bark-device-keys"
            name="device_keys"
            className="mt-1 h-20 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
            value={deviceKeysText}
            onChange={(e) => setDeviceKeysText(e.target.value)}
            disabled={!canCreate || submitting}
          />
        </label>
      ) : (
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Device key</div>
          <input
            id="bark-device-key"
            name="device_key"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
            value={deviceKey}
            onChange={(e) => setDeviceKey(e.target.value)}
            disabled={!canCreate || submitting}
          />
        </label>
      )}
      <label className="block md:col-span-2">
        <div className="text-xs font-medium text-muted-foreground">Default payload JSON</div>
        <textarea
          id="bark-default-payload-json"
          name="default_payload_json"
          className="mt-1 h-24 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 font-mono text-xs"
          value={defaultPayloadJson}
          onChange={(e) => setDefaultPayloadJson(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>
    </>
  );
}

export function validateBarkConfig(state: Omit<BarkChannelFormProps, "canCreate" | "submitting" | "setServerBaseUrl" | "setDeviceKey" | "setUseDeviceKeys" | "setDeviceKeysText" | "setDefaultPayloadJson">): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  let baseUrl = state.serverBaseUrl.trim();
  let deviceKey = state.deviceKey.trim();
  if (!baseUrl) {
    return { ok: false, error: "Server base URL is required." };
  }

  if (baseUrl.endsWith("/push")) {
    baseUrl = baseUrl.slice(0, -"/push".length);
  }

  const split = trySplitBarkUrl(baseUrl);
  if (split) {
    baseUrl = split.serverBaseUrl;
    if (!state.useDeviceKeys && !deviceKey) {
      deviceKey = split.deviceKey;
    }
  }

  let deviceKeys: string[] | null = null;
  if (state.useDeviceKeys) {
    const keys = state.deviceKeysText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (keys.length === 0) {
      return { ok: false, error: "At least one device key is required." };
    }
    deviceKeys = keys;
  } else {
    if (!deviceKey) {
      return { ok: false, error: "Device key is required (you can also paste a full Bark key URL). " };
    }
  }

  const parsed = parseOptionalJsonObject(state.defaultPayloadJson);
  if (!parsed.ok) {
    return { ok: false, error: `Default payload JSON: ${parsed.error}` };
  }
  return {
    ok: true,
    config: {
      server_base_url: baseUrl,
      device_key: state.useDeviceKeys ? undefined : deviceKey,
      device_keys: state.useDeviceKeys ? deviceKeys : undefined,
      default_payload_json: parsed.value,
    },
  };
}
