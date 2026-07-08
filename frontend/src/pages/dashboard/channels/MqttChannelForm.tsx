import type { MqttFormValues } from "./formState";

export interface MqttChannelFormProps {
  submitting: boolean;
  values: MqttFormValues;
  onChange: (values: MqttFormValues) => void;
}

export function MqttChannelForm({
  submitting,
  values,
  onChange,
}: MqttChannelFormProps) {
  return (
    <>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Broker host</div>
        <input
          id="mqtt-broker-host"
          name="broker_host"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          placeholder="mqtt.example.com"
          value={values.brokerHost}
          onChange={(e) => onChange({ ...values, brokerHost: e.target.value })}
          disabled={submitting}
        />
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Broker port</div>
        <input
          id="mqtt-broker-port"
          name="broker_port"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          type="number"
          min={1}
          max={65535}
          value={values.brokerPort}
          onChange={(e) => onChange({ ...values, brokerPort: e.target.value })}
          disabled={submitting}
        />
      </label>
      <label className="block md:col-span-2">
        <div className="text-xs font-medium text-muted-foreground">Topic</div>
        <input
          id="mqtt-topic"
          name="topic"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          placeholder="herald/messages"
          value={values.topic}
          onChange={(e) => onChange({ ...values, topic: e.target.value })}
          disabled={submitting}
        />
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Username (optional)</div>
        <input
          id="mqtt-username"
          name="username"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={values.username}
          onChange={(e) => onChange({ ...values, username: e.target.value })}
          disabled={submitting}
        />
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Password (optional)</div>
        <input
          id="mqtt-password"
          name="password"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          type="password"
          value={values.password}
          onChange={(e) => onChange({ ...values, password: e.target.value })}
          disabled={submitting}
        />
      </label>

      <label className="flex items-end gap-2">
        <input
          id="mqtt-tls"
          name="tls"
          type="checkbox"
          checked={values.tls}
          onChange={(e) => onChange({ ...values, tls: e.target.checked })}
          disabled={submitting}
        />
        <span className="text-sm text-muted-foreground">TLS</span>
      </label>
      <label className="flex items-end gap-2">
        <input
          id="mqtt-tls-insecure"
          name="tls_insecure"
          type="checkbox"
          checked={values.tlsInsecure}
          onChange={(e) => onChange({ ...values, tlsInsecure: e.target.checked })}
          disabled={submitting || !values.tls}
        />
        <span className="text-sm text-muted-foreground">TLS insecure</span>
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">QoS</div>
        <select
          id="mqtt-qos"
          name="qos"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={values.qos}
          onChange={(e) => onChange({ ...values, qos: e.target.value })}
          disabled={submitting}
        >
          <option value="0">0</option>
          <option value="1">1</option>
          <option value="2">2</option>
        </select>
      </label>
      <label className="flex items-end gap-2">
        <input
          id="mqtt-retain"
          name="retain"
          type="checkbox"
          checked={values.retain}
          onChange={(e) => onChange({ ...values, retain: e.target.checked })}
          disabled={submitting}
        />
        <span className="text-sm text-muted-foreground">Retain</span>
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Client id (optional)</div>
        <input
          id="mqtt-client-id"
          name="client_id"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          value={values.clientId}
          onChange={(e) => onChange({ ...values, clientId: e.target.value })}
          disabled={submitting}
        />
      </label>
      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Keepalive (seconds)</div>
        <input
          id="mqtt-keepalive-seconds"
          name="keepalive_seconds"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm font-mono"
          type="number"
          min={1}
          max={3600}
          value={values.keepaliveSeconds}
          onChange={(e) => onChange({ ...values, keepaliveSeconds: e.target.value })}
          disabled={submitting}
        />
      </label>
    </>
  );
}

export function validateMqttConfig(state: MqttFormValues): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  if (!state.brokerHost.trim()) {
    return { ok: false, error: "Broker host is required." };
  }
  if (!state.topic.trim()) {
    return { ok: false, error: "Topic is required." };
  }
  const port = parseInt(state.brokerPort || "0", 10);
  if (!port || port < 1 || port > 65535) {
    return { ok: false, error: "Broker port must be between 1 and 65535." };
  }
  const qos = parseInt(state.qos || "0", 10);
  if (qos < 0 || qos > 2) {
    return { ok: false, error: "QoS must be 0, 1, or 2." };
  }
  const keepalive = parseInt(state.keepaliveSeconds || "0", 10);
  if (!keepalive || keepalive < 1 || keepalive > 3600) {
    return { ok: false, error: "Keepalive must be between 1 and 3600." };
  }
  const user = state.username.trim();
  const pass = state.password;
  if ((user && !pass.trim()) || (pass.trim() && !user)) {
    return { ok: false, error: "Username and password must be set together." };
  }

  return {
    ok: true,
    config: {
      broker_host: state.brokerHost.trim(),
      broker_port: port,
      topic: state.topic.trim(),
      username: user || undefined,
      password: user ? pass : undefined,
      tls: state.tls,
      tls_insecure: state.tlsInsecure,
      qos,
      retain: state.retain,
      client_id: state.clientId.trim() || undefined,
      keepalive_seconds: keepalive,
    },
  };
}
