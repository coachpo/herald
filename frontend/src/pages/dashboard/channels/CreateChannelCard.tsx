import { useCallback, useState } from "react";

import { readApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";

import { BarkChannelForm } from "./BarkChannelForm";
import { GotifyChannelForm } from "./GotifyChannelForm";
import { MqttChannelForm } from "./MqttChannelForm";
import { NtfyChannelForm } from "./NtfyChannelForm";
import {
  buildChannelConfig,
  type ChannelType,
  useChannelFormState,
} from "./formState";

export interface CreateChannelCardProps {
  canCreate: boolean;
  onCreated: () => void;
}

export function CreateChannelCard({ canCreate, onCreated }: CreateChannelCardProps) {
  const auth = useAuth();
  const form = useChannelFormState();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    setError(null);
    setSubmitting(true);
    try {
      if (!form.name.trim()) {
        setError("Name is required.");
        return;
      }

      const config = buildChannelConfig(form);
      if (!config.ok) {
        setError(config.error);
        return;
      }

      const res = await authedFetch(auth, "/api/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: form.channelType, name: form.name, config: config.config }),
      });
      if (!res.ok) {
        setError((await readApiError(res)).message);
        return;
      }

      form.resetForm();
      onCreated();
    } finally {
      setSubmitting(false);
    }
  }, [auth, form, onCreated]);

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-sm font-semibold">Create channel</div>

      {error && (
        <div className="mt-3 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {error}
        </div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Type</div>
          <select
            id="channel-type"
            name="type"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={form.channelType}
            onChange={(e) => form.setChannelType(e.target.value as ChannelType)}
            disabled={!canCreate || submitting}
          >
            <option value="bark">bark</option>
            <option value="ntfy">ntfy</option>
            <option value="mqtt">mqtt</option>
            <option value="gotify">gotify</option>
          </select>
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Name</div>
          <input
            id="channel-name"
            name="name"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={form.name}
            onChange={(e) => form.setName(e.target.value)}
            disabled={!canCreate || submitting}
          />
        </label>

        {form.channelType === "bark" && (
          <BarkChannelForm
            canCreate={canCreate}
            submitting={submitting}
            serverBaseUrl={form.barkServerBaseUrl}
            setServerBaseUrl={form.setBarkServerBaseUrl}
            deviceKey={form.barkDeviceKey}
            setDeviceKey={form.setBarkDeviceKey}
            useDeviceKeys={form.barkUseDeviceKeys}
            setUseDeviceKeys={form.setBarkUseDeviceKeys}
            deviceKeysText={form.barkDeviceKeysText}
            setDeviceKeysText={form.setBarkDeviceKeysText}
            defaultPayloadJson={form.barkDefaultPayloadJson}
            setDefaultPayloadJson={form.setBarkDefaultPayloadJson}
          />
        )}

        {form.channelType === "ntfy" && (
          <NtfyChannelForm
            canCreate={canCreate}
            submitting={submitting}
            serverBaseUrl={form.ntfyServerBaseUrl}
            setServerBaseUrl={form.setNtfyServerBaseUrl}
            topic={form.ntfyTopic}
            setTopic={form.setNtfyTopic}
            authMode={form.ntfyAuthMode}
            setAuthMode={form.setNtfyAuthMode}
            accessToken={form.ntfyAccessToken}
            setAccessToken={form.setNtfyAccessToken}
            username={form.ntfyUsername}
            setUsername={form.setNtfyUsername}
            password={form.ntfyPassword}
            setPassword={form.setNtfyPassword}
            defaultHeadersJson={form.ntfyDefaultHeadersJson}
            setDefaultHeadersJson={form.setNtfyDefaultHeadersJson}
          />
        )}

        {form.channelType === "mqtt" && (
          <MqttChannelForm
            canCreate={canCreate}
            submitting={submitting}
            brokerHost={form.mqttBrokerHost}
            setBrokerHost={form.setMqttBrokerHost}
            brokerPort={form.mqttBrokerPort}
            setBrokerPort={form.setMqttBrokerPort}
            topic={form.mqttTopic}
            setTopic={form.setMqttTopic}
            username={form.mqttUsername}
            setUsername={form.setMqttUsername}
            password={form.mqttPassword}
            setPassword={form.setMqttPassword}
            tls={form.mqttTls}
            setTls={form.setMqttTls}
            tlsInsecure={form.mqttTlsInsecure}
            setTlsInsecure={form.setMqttTlsInsecure}
            qos={form.mqttQos}
            setQos={form.setMqttQos}
            retain={form.mqttRetain}
            setRetain={form.setMqttRetain}
            clientId={form.mqttClientId}
            setClientId={form.setMqttClientId}
            keepaliveSeconds={form.mqttKeepaliveSeconds}
            setKeepaliveSeconds={form.setMqttKeepaliveSeconds}
          />
        )}

        {form.channelType === "gotify" && (
          <GotifyChannelForm
            canCreate={canCreate}
            submitting={submitting}
            serverBaseUrl={form.gotifyServerBaseUrl}
            setServerBaseUrl={form.setGotifyServerBaseUrl}
            appToken={form.gotifyAppToken}
            setAppToken={form.setGotifyAppToken}
            defaultPriority={form.gotifyDefaultPriority}
            setDefaultPriority={form.setGotifyDefaultPriority}
            defaultExtrasJson={form.gotifyDefaultExtrasJson}
            setDefaultExtrasJson={form.setGotifyDefaultExtrasJson}
          />
        )}
      </div>

      <div className="mt-3">
        <button
          type="button"
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={!canCreate || submitting}
          onClick={() => void submit()}
        >
          Create
        </button>

        {!canCreate && (
          <div className="mt-2 text-xs text-warning">Verify your email to create channels.</div>
        )}
      </div>
    </div>
  );
}
