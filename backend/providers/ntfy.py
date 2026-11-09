"""ntfy JSON publishing avoids non-ASCII text in HTTP headers."""
from .http import post

async def send(config: dict, message: dict, *, timeout: float) -> dict:
    payload = {"topic": config["topic"], "message": message["body"], "priority": message.get("priority", 3)}
    if message.get("title"):
        payload["title"] = message["title"]
    headers = {}
    if config.get("access_token"):
        headers["Authorization"] = "Bearer " + config["access_token"]
    return await post(config["server_base_url"], json=payload, headers=headers, timeout=timeout)
