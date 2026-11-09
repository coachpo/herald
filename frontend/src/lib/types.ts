export type Kind = "bark" | "ntfy" | "mqtt" | "gotify";
export type Config = Record<string, string | number | boolean>;
export type Target = {
  id: string;
  name: string;
  kind: Kind;
  config: Config;
  is_default: boolean;
  enabled: boolean;
};
export type TargetInput = Omit<Target, "id">;
export type Delivery = {
  id: string;
  target_id: string;
  target_name: string;
  status: "pending" | "sending" | "retry" | "sent" | "failed";
  attempts: number;
  last_error: string | null;
  available_at: string | null;
  completed_at: string | null;
};
export type Message = {
  id: string;
  title: string;
  body: string;
  priority: number;
  received_at: string;
  deliveries: Delivery[];
};
export type MessagePage = { messages: Message[]; next_cursor?: string | null };
export type Settings = {
  ingest_path: string;
  retention_days: number;
  max_attempts: number;
};
