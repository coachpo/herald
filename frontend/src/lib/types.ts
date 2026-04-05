export type ApiError = {
  code: string;
  message: string;
  details?: unknown;
};

export type User = {
  id: string;
  email: string;
  email_verified_at: string | null;
  created_at: string;
};

export type IngestEndpoint = {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type Channel = {
  id: string;
  type: "bark" | "ntfy" | "mqtt" | "gotify";
  name: string;
  created_at: string;
  disabled_at: string | null;
};

export type BarkChannelConfig = {
  server_base_url: string;
  device_key?: string | null;
  device_keys?: string[] | null;
  default_payload_json?: Record<string, unknown>;
};

export type NtfyChannelConfig = {
  server_base_url: string;
  topic: string;
  access_token?: string | null;
  username?: string | null;
  password?: string | null;
  default_headers_json?: Record<string, unknown>;
};

export type MqttChannelConfig = {
  broker_host: string;
  broker_port?: number | null;
  topic: string;
  username?: string | null;
  password?: string | null;
  tls?: boolean | null;
  tls_insecure?: boolean | null;
  qos?: number | null;
  retain?: boolean | null;
  client_id?: string | null;
  keepalive_seconds?: number | null;
};

export type GotifyChannelConfig = {
  server_base_url: string;
  app_token: string;
  default_priority?: number | null;
  default_extras_json?: Record<string, unknown>;
  default_payload_json?: Record<string, unknown>;
};

export type Rule = {
  id: string;
  name: string;
  enabled: boolean;
  channel_id: string;
  filter: Record<string, unknown>;
  payload_template: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type MessageSummary = {
  id: string;
  ingest_endpoint_id: string;
  received_at: string;
  title: string | null;
  body_preview: string;
  group: string | null;
  priority: number;
  tags: string[];
  deliveries: {
    queued: number;
    sending: number;
    retry: number;
    sent: number;
    failed: number;
  };
};

export type MessageDetail = {
  id: string;
  ingest_endpoint_id: string;
  received_at: string;
  title: string | null;
  body: string;
  group: string | null;
  priority: number;
  tags: string[];
  url: string | null;
  extras: Record<string, string>;
  content_type: string | null;
  headers: Record<string, string>;
  query: Record<string, string>;
  remote_ip: string;
  user_agent: string | null;
  deleted_at: string | null;
};

export type Delivery = {
  id: string;
  message_id: string;
  rule_id: string;
  rule_name?: string | null;
  channel_id: string;
  channel_name?: string | null;
  status: "queued" | "sending" | "retry" | "sent" | "failed";
  attempt_count: number;
  next_attempt_at: string | null;
  sent_at: string | null;
  last_error: string | null;
  provider_response: unknown;
};
