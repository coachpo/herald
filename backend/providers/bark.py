"""Bark JSON /push: success acknowledges the server, not the device."""
from .http import post

async def send(config: dict, message: dict, *, timeout: float) -> dict:
    payload = {"device_key": config["device_key"], "body": message["body"]}
    if message.get("title"):
        payload["title"] = message["title"]
    return await post(config["server_base_url"] + "/push", json=payload, timeout=timeout)
