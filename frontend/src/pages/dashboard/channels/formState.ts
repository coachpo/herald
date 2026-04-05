import { useCallback, useState } from "react";

import type { Channel } from "@/lib/types";

import { validateBarkConfig } from "./BarkChannelForm";
import { validateGotifyConfig } from "./GotifyChannelForm";
import { validateMqttConfig } from "./MqttChannelForm";
import { validateNtfyConfig } from "./NtfyChannelForm";

export type ChannelType = Channel["type"];

export function useChannelFormState() {
  const [channelType, setChannelType] = useState<ChannelType>("bark");
  const [name, setName] = useState("");

  const [barkServerBaseUrl, setBarkServerBaseUrl] = useState("");
  const [barkDeviceKey, setBarkDeviceKey] = useState("");
  const [barkUseDeviceKeys, setBarkUseDeviceKeys] = useState(false);
  const [barkDeviceKeysText, setBarkDeviceKeysText] = useState("");
  const [barkDefaultPayloadJson, setBarkDefaultPayloadJson] = useState("{}");

  const [ntfyServerBaseUrl, setNtfyServerBaseUrl] = useState("");
  const [ntfyTopic, setNtfyTopic] = useState("");
  const [ntfyAuthMode, setNtfyAuthMode] = useState<"none" | "bearer" | "basic">("none");
  const [ntfyAccessToken, setNtfyAccessToken] = useState("");
  const [ntfyUsername, setNtfyUsername] = useState("");
  const [ntfyPassword, setNtfyPassword] = useState("");
  const [ntfyDefaultHeadersJson, setNtfyDefaultHeadersJson] = useState("{}");

  const [mqttBrokerHost, setMqttBrokerHost] = useState("");
  const [mqttBrokerPort, setMqttBrokerPort] = useState("1883");
  const [mqttTopic, setMqttTopic] = useState("");
  const [mqttUsername, setMqttUsername] = useState("");
  const [mqttPassword, setMqttPassword] = useState("");
  const [mqttTls, setMqttTls] = useState(false);
  const [mqttTlsInsecure, setMqttTlsInsecure] = useState(false);
  const [mqttQos, setMqttQos] = useState("0");
  const [mqttRetain, setMqttRetain] = useState(false);
  const [mqttClientId, setMqttClientId] = useState("");
  const [mqttKeepaliveSeconds, setMqttKeepaliveSeconds] = useState("60");

  const [gotifyServerBaseUrl, setGotifyServerBaseUrl] = useState("");
  const [gotifyAppToken, setGotifyAppToken] = useState("");
  const [gotifyDefaultPriority, setGotifyDefaultPriority] = useState("");
  const [gotifyDefaultExtrasJson, setGotifyDefaultExtrasJson] = useState("{}");

  const resetForm = useCallback(() => {
    setChannelType("bark");
    setName("");

    setBarkServerBaseUrl("");
    setBarkDeviceKey("");
    setBarkUseDeviceKeys(false);
    setBarkDeviceKeysText("");
    setBarkDefaultPayloadJson("{}");

    setNtfyServerBaseUrl("");
    setNtfyTopic("");
    setNtfyAuthMode("none");
    setNtfyAccessToken("");
    setNtfyUsername("");
    setNtfyPassword("");
    setNtfyDefaultHeadersJson("{}");

    setMqttBrokerHost("");
    setMqttBrokerPort("1883");
    setMqttTopic("");
    setMqttUsername("");
    setMqttPassword("");
    setMqttTls(false);
    setMqttTlsInsecure(false);
    setMqttQos("0");
    setMqttRetain(false);
    setMqttClientId("");
    setMqttKeepaliveSeconds("60");

    setGotifyServerBaseUrl("");
    setGotifyAppToken("");
    setGotifyDefaultPriority("");
    setGotifyDefaultExtrasJson("{}");
  }, []);

  return {
    channelType,
    setChannelType,
    name,
    setName,
    barkServerBaseUrl,
    setBarkServerBaseUrl,
    barkDeviceKey,
    setBarkDeviceKey,
    barkUseDeviceKeys,
    setBarkUseDeviceKeys,
    barkDeviceKeysText,
    setBarkDeviceKeysText,
    barkDefaultPayloadJson,
    setBarkDefaultPayloadJson,
    ntfyServerBaseUrl,
    setNtfyServerBaseUrl,
    ntfyTopic,
    setNtfyTopic,
    ntfyAuthMode,
    setNtfyAuthMode,
    ntfyAccessToken,
    setNtfyAccessToken,
    ntfyUsername,
    setNtfyUsername,
    ntfyPassword,
    setNtfyPassword,
    ntfyDefaultHeadersJson,
    setNtfyDefaultHeadersJson,
    mqttBrokerHost,
    setMqttBrokerHost,
    mqttBrokerPort,
    setMqttBrokerPort,
    mqttTopic,
    setMqttTopic,
    mqttUsername,
    setMqttUsername,
    mqttPassword,
    setMqttPassword,
    mqttTls,
    setMqttTls,
    mqttTlsInsecure,
    setMqttTlsInsecure,
    mqttQos,
    setMqttQos,
    mqttRetain,
    setMqttRetain,
    mqttClientId,
    setMqttClientId,
    mqttKeepaliveSeconds,
    setMqttKeepaliveSeconds,
    gotifyServerBaseUrl,
    setGotifyServerBaseUrl,
    gotifyAppToken,
    setGotifyAppToken,
    gotifyDefaultPriority,
    setGotifyDefaultPriority,
    gotifyDefaultExtrasJson,
    setGotifyDefaultExtrasJson,
    resetForm,
  };
}

export type ChannelFormState = ReturnType<typeof useChannelFormState>;

export function buildChannelConfig(
  form: ChannelFormState,
): { ok: true; config: Record<string, unknown> } | { ok: false; error: string } {
  if (form.channelType === "bark") {
    return validateBarkConfig({
      serverBaseUrl: form.barkServerBaseUrl,
      deviceKey: form.barkDeviceKey,
      useDeviceKeys: form.barkUseDeviceKeys,
      deviceKeysText: form.barkDeviceKeysText,
      defaultPayloadJson: form.barkDefaultPayloadJson,
    });
  }

  if (form.channelType === "ntfy") {
    return validateNtfyConfig({
      serverBaseUrl: form.ntfyServerBaseUrl,
      topic: form.ntfyTopic,
      authMode: form.ntfyAuthMode,
      accessToken: form.ntfyAccessToken,
      username: form.ntfyUsername,
      password: form.ntfyPassword,
      defaultHeadersJson: form.ntfyDefaultHeadersJson,
    });
  }

  if (form.channelType === "mqtt") {
    return validateMqttConfig({
      brokerHost: form.mqttBrokerHost,
      brokerPort: form.mqttBrokerPort,
      topic: form.mqttTopic,
      username: form.mqttUsername,
      password: form.mqttPassword,
      tls: form.mqttTls,
      tlsInsecure: form.mqttTlsInsecure,
      qos: form.mqttQos,
      retain: form.mqttRetain,
      clientId: form.mqttClientId,
      keepaliveSeconds: form.mqttKeepaliveSeconds,
    });
  }

  return validateGotifyConfig({
    serverBaseUrl: form.gotifyServerBaseUrl,
    appToken: form.gotifyAppToken,
    defaultPriority: form.gotifyDefaultPriority,
    defaultExtrasJson: form.gotifyDefaultExtrasJson,
  });
}
