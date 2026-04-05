export interface MqttChannelFormProps {
  canCreate: boolean;
  submitting: boolean;
  brokerHost: string;
  setBrokerHost: (val: string) => void;
  brokerPort: string;
  setBrokerPort: (val: string) => void;
  topic: string;
  setTopic: (val: string) => void;
  username: string;
  setUsername: (val: string) => void;
  password: string;
  setPassword: (val: string) => void;
  tls: boolean;
  setTls: (val: boolean) => void;
  tlsInsecure: boolean;
  setTlsInsecure: (val: boolean) => void;
  qos: string;
  setQos: (val: string) => void;
  retain: boolean;
  setRetain: (val: boolean) => void;
  clientId: string;
  setClientId: (val: string) => void;
  keepaliveSeconds: string;
  setKeepaliveSeconds: (val: string) => void;
}

export function MqttChannelForm({
  canCreate,
  submitting,
  brokerHost,
  setBrokerHost,
  brokerPort,
  setBrokerPort,
  topic,
  setTopic,
  username,
  setUsername,
  password,
  setPassword,
  tls,
  setTls,
  tlsInsecure,
  setTlsInsecure,
  qos,
  setQos,
  retain,
  setRetain,
  clientId,
  setClientId,
  keepaliveSeconds,
  setKeepaliveSeconds,
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
          value={brokerHost}
          onChange={(e) => setBrokerHost(e.target.value)}
          disabled={!canCreate || submitting}
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
          value={brokerPort}
          onChange={(e) => setBrokerPort(e.target.value)}
          disabled={!canCreate || submitting}
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
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">Username (optional)</div>
        <input
          id="mqtt-username"
          name="username"
          autoComplete="off"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={!canCreate || submitting}
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
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>

      <label className="flex items-end gap-2">
        <input
          id="mqtt-tls"
          name="tls"
          type="checkbox"
          checked={tls}
          onChange={(e) => setTls(e.target.checked)}
          disabled={!canCreate || submitting}
        />
        <span className="text-sm text-muted-foreground">TLS</span>
      </label>
      <label className="flex items-end gap-2">
        <input
          id="mqtt-tls-insecure"
          name="tls_insecure"
          type="checkbox"
          checked={tlsInsecure}
          onChange={(e) => setTlsInsecure(e.target.checked)}
          disabled={!canCreate || submitting || !tls}
        />
        <span className="text-sm text-muted-foreground">TLS insecure</span>
      </label>

      <label className="block">
        <div className="text-xs font-medium text-muted-foreground">QoS</div>
        <select
          id="mqtt-qos"
          name="qos"
          className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
          value={qos}
          onChange={(e) => setQos(e.target.value)}
          disabled={!canCreate || submitting}
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
          checked={retain}
          onChange={(e) => setRetain(e.target.checked)}
          disabled={!canCreate || submitting}
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
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          disabled={!canCreate || submitting}
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
          value={keepaliveSeconds}
          onChange={(e) => setKeepaliveSeconds(e.target.value)}
          disabled={!canCreate || submitting}
        />
      </label>
    </>
  );
}

export function validateMqttConfig(state: Omit<MqttChannelFormProps, "canCreate" | "submitting" | "setBrokerHost" | "setBrokerPort" | "setTopic" | "setUsername" | "setPassword" | "setTls" | "setTlsInsecure" | "setQos" | "setRetain" | "setClientId" | "setKeepaliveSeconds">): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
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
