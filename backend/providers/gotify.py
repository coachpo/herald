"""Gotify provider - async HTTP implementation with httpx."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..core.ssrf import assert_ssrf_safe
from ..core.template import build_template_context, render_template

# Herald priority (1-5) → Gotify priority (0-10)
_PRIORITY_MAP = {1: 0, 2: 2, 3: 5, 4: 7, 5: 10}


def build_gotify_payload(
    *,
    channel_config: dict[str, Any],
    payload_template: dict[str, Any],
    message: dict[str, Any],
    ingest_endpoint: dict[str, Any],
) -> dict:
    """Build Gotify message payload from channel config, template, and message."""
    default_extras = channel_config.get("default_extras_json") or {}
    default_priority = channel_config.get("default_priority")
    default_payload = channel_config.get("default_payload_json") or {}

    ctx = build_template_context(message, ingest_endpoint)
    rendered = render_template(payload_template, ctx)
    rendered_dict = rendered if isinstance(rendered, dict) else {}

    payload: dict[str, Any] = {}
    if isinstance(default_payload, dict):
        payload.update(default_payload)

    # Extract message body (required by Gotify)
    body_val = (
        rendered_dict.get("body")
        or rendered_dict.get("message")
        or rendered_dict.get("text")
    )
    if body_val is None:
        body_val = message.get("body") or ""
    payload["message"] = str(body_val)

    # Extract title (optional)
    title_val = rendered_dict.get("title")
    if title_val is not None:
        payload["title"] = str(title_val)
    elif message.get("title"):
        payload["title"] = message["title"]

    # Priority mapping
    prio_val = rendered_dict.get("priority")
    if prio_val is not None:
        try:
            payload["priority"] = int(prio_val)
        except (ValueError, TypeError):
            pass

    if "priority" not in payload:
        msg_priority = message.get("priority")
        if msg_priority and msg_priority != 3:
            payload["priority"] = _PRIORITY_MAP.get(msg_priority, 5)
        elif default_priority is not None:
            payload["priority"] = int(default_priority)

    # Extras (markdown, click URL, etc.)
    extras: dict[str, Any] = {}
    if isinstance(default_extras, dict):
        extras.update(default_extras)

    rendered_extras = rendered_dict.get("extras")
    if isinstance(rendered_extras, dict):
        extras.update(rendered_extras)

    # Support markdown flag
    markdown = rendered_dict.get("markdown")
    if isinstance(markdown, bool) and markdown:
        extras.setdefault("client::display", {})["contentType"] = "text/markdown"

    # Support click URL
    click_url = rendered_dict.get("click") or rendered_dict.get("url")
    if click_url:
        extras.setdefault("client::notification", {})["click"] = {"url": str(click_url)}

    if extras:
        payload["extras"] = extras

    return payload


async def send_gotify_push(
    *,
    server_base_url: str,
    app_token: str,
    payload: dict,
    timeout: float = 5.0,
    block_private_networks: bool = True,
) -> tuple[bool, dict]:
    """Send message to Gotify server via async HTTP."""
    url = server_base_url.rstrip("/") + "/message"
    assert_ssrf_safe(url, block_private_networks=block_private_networks)

    headers = {
        "Content-Type": "application/json",
        "X-Gotify-Key": app_token,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=timeout)

    meta: dict = {
        "http_status": resp.status_code,
    }

    content_type = (
        (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    )
    body_bytes = resp.content or b""
    snippet = body_bytes[:2048]
    try:
        meta["body_snippet"] = snippet.decode("utf-8", errors="replace")
    except Exception:
        meta["body_snippet"] = repr(snippet)

    if content_type == "application/json":
        try:
            meta["json"] = resp.json()
        except json.JSONDecodeError:
            pass

    ok = 200 <= resp.status_code < 300
    return ok, meta
