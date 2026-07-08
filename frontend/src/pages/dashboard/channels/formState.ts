import { useCallback, useState } from "react";

import type { Channel } from "@/lib/types";

import { validateBarkConfig } from "./BarkChannelForm";
import { validateGotifyConfig } from "./GotifyChannelForm";
import { validateMqttConfig } from "./MqttChannelForm";
import { validateNtfyConfig } from "./NtfyChannelForm";

export type ChannelType = Channel["type"];

export type CommonFormValues = {
  channelType: ChannelType;
  name: string;
};

export type BarkFormValues = {
  serverBaseUrl: string;
  deviceKey: string;
  useDeviceKeys: boolean;
  deviceKeysText: string;
  defaultPayloadJson: string;
};

export type NtfyFormValues = {
  serverBaseUrl: string;
  topic: string;
  authMode: "none" | "bearer" | "basic";
  accessToken: string;
  username: string;
  password: string;
  defaultHeadersJson: string;
};

export type MqttFormValues = {
  brokerHost: string;
  brokerPort: string;
  topic: string;
  username: string;
  password: string;
  tls: boolean;
  tlsInsecure: boolean;
  qos: string;
  retain: boolean;
  clientId: string;
  keepaliveSeconds: string;
};

export type GotifyFormValues = {
  serverBaseUrl: string;
  appToken: string;
  defaultPriority: string;
  defaultExtrasJson: string;
};

export const EMPTY_COMMON: CommonFormValues = { channelType: "bark", name: "" };
export const EMPTY_BARK: BarkFormValues = {
  serverBaseUrl: "",
  deviceKey: "",
  useDeviceKeys: false,
  deviceKeysText: "",
  defaultPayloadJson: "{}",
};
export const EMPTY_NTFY: NtfyFormValues = {
  serverBaseUrl: "",
  topic: "",
  authMode: "none",
  accessToken: "",
  username: "",
  password: "",
  defaultHeadersJson: "{}",
};
export const EMPTY_MQTT: MqttFormValues = {
  brokerHost: "",
  brokerPort: "1883",
  topic: "",
  username: "",
  password: "",
  tls: false,
  tlsInsecure: false,
  qos: "0",
  retain: false,
  clientId: "",
  keepaliveSeconds: "60",
};
export const EMPTY_GOTIFY: GotifyFormValues = {
  serverBaseUrl: "",
  appToken: "",
  defaultPriority: "",
  defaultExtrasJson: "{}",
};

export function useChannelFormState() {
  const [common, setCommon] = useState<CommonFormValues>(EMPTY_COMMON);
  const [bark, setBark] = useState<BarkFormValues>(EMPTY_BARK);
  const [ntfy, setNtfy] = useState<NtfyFormValues>(EMPTY_NTFY);
  const [mqtt, setMqtt] = useState<MqttFormValues>(EMPTY_MQTT);
  const [gotify, setGotify] = useState<GotifyFormValues>(EMPTY_GOTIFY);

  const resetForm = useCallback(() => {
    setCommon(EMPTY_COMMON);
    setBark(EMPTY_BARK);
    setNtfy(EMPTY_NTFY);
    setMqtt(EMPTY_MQTT);
    setGotify(EMPTY_GOTIFY);
  }, []);

  return {
    common,
    setCommon,
    bark,
    setBark,
    ntfy,
    setNtfy,
    mqtt,
    setMqtt,
    gotify,
    setGotify,
    resetForm,
  };
}

export type ChannelFormState = ReturnType<typeof useChannelFormState>;

export function buildChannelConfig(
  form: ChannelFormState,
): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  if (form.common.channelType === "bark") return validateBarkConfig(form.bark);
  if (form.common.channelType === "ntfy") return validateNtfyConfig(form.ntfy);
  if (form.common.channelType === "mqtt") return validateMqttConfig(form.mqtt);
  return validateGotifyConfig(form.gotify);
}
