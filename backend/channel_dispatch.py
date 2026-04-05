from __future__ import annotations

import asyncio
from typing import Any

from .providers import bark, gotify, mqtt, ntfy


async def dispatch_channel_message(
    *,
    channel_type: str,
    config: dict[str, Any],
    payload_template: dict[str, Any],
    message: dict[str, Any],
    ingest_endpoint: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    normalized_type = str(channel_type).strip()

    if normalized_type == "bark":
        payload = bark.build_bark_payload(
            channel_config=config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=ingest_endpoint,
        )
        ok, meta = await bark.send_bark_push(
            server_base_url=config["server_base_url"],
            payload=payload,
        )
        return bool(ok), dict(meta)

    if normalized_type == "ntfy":
        url, body_bytes, headers, auth = ntfy.build_ntfy_request(
            channel_config=config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=ingest_endpoint,
        )
        ok, meta = await ntfy.send_ntfy_publish(
            url=url,
            body=body_bytes,
            headers=headers,
            auth=auth,
        )
        return bool(ok), dict(meta)

    if normalized_type == "mqtt":
        ok, meta = await asyncio.to_thread(
            mqtt.send_mqtt_publish,
            broker_host=config["broker_host"],
            broker_port=config.get("broker_port", 1883),
            topic=config["topic"],
            payload=message.get("body", ""),
            username=config.get("username"),
            password=config.get("password"),
            qos=config.get("qos", 0),
            retain=config.get("retain", False),
            tls=config.get("tls", False),
            tls_insecure=config.get("tls_insecure", False),
            client_id=config.get("client_id"),
            keepalive_seconds=config.get("keepalive_seconds", 60),
        )
        return bool(ok), dict(meta)

    if normalized_type == "gotify":
        payload = gotify.build_gotify_payload(
            channel_config=config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=ingest_endpoint,
        )
        server_base_url = str(config.get("server_base_url") or "").strip()
        app_token = str(config.get("app_token") or "").strip()
        if not server_base_url:
            raise ValueError("missing_server_base_url")
        if not app_token:
            raise ValueError("missing_app_token")
        ok, meta = await gotify.send_gotify_push(
            server_base_url=server_base_url,
            app_token=app_token,
            payload=payload,
        )
        return bool(ok), dict(meta)

    raise ValueError(f"unsupported_channel_type: {normalized_type}")


__all__ = ["dispatch_channel_message"]
