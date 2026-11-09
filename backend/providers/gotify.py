"""Gotify /message: success acknowledges server acceptance only."""
from .http import post

async def send(config: dict, message: dict, *, timeout: float) -> dict:
    payload = {"message": message["body"], "priority": {1: 0, 2: 2, 3: 5, 4: 7, 5: 10}[message.get("priority", 3)]}
    if message.get("title"):
        payload["title"] = message["title"]
    return await post(config["server_base_url"] + "/message", json=payload,
                      headers={"X-Gotify-Key": config["app_token"]}, timeout=timeout)
