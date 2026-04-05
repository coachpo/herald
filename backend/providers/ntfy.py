"""ntfy provider - async HTTP implementation with httpx."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx

from ..core.ssrf import assert_ssrf_safe
from ..core.template import build_template_context, render_template


def build_topic_url(server_base_url: str, topic: str) -> str:
    base = server_base_url.rstrip("/") + "/"
    return urljoin(base, str(topic).lstrip("/"))


def _coerce_header_value(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return str(v)


def build_ntfy_request(
    *,
    channel_config: dict[str, Any],
    payload_template: dict[str, Any],
    message: dict[str, Any],
    ingest_endpoint: dict[str, Any],
    block_private_networks: bool = True,
) -> tuple[str, bytes, dict[str, str], tuple[str, str] | None]:
    """Build ntfy request from channel config, template, and message."""
    server_base_url = str(channel_config.get("server_base_url") or "").strip()
    topic = str(channel_config.get("topic") or "").strip()
    if not server_base_url:
        raise ValueError("missing_server_base_url")
    if not topic:
        raise ValueError("missing_topic")

    url = build_topic_url(server_base_url, topic)
    assert_ssrf_safe(url, block_private_networks=block_private_networks)

    ctx = build_template_context(message, ingest_endpoint)
    rendered = render_template(payload_template, ctx)
    rendered_dict = rendered if isinstance(rendered, dict) else {}

    body_val = rendered_dict.get("body")
    if body_val is None:
        body_val = rendered_dict.get("message")
    if body_val is None:
        body_val = rendered_dict.get("text")
    body = _coerce_header_value(body_val) if body_val is not None else None
    if body is None:
        body = message.get("body") or ""

    headers: dict[str, str] = {}
    default_headers = channel_config.get("default_headers_json")
    if isinstance(default_headers, dict):
        for k, v in default_headers.items():
            kk = str(k).strip()
            vv = _coerce_header_value(v)
            if kk and vv is not None:
                headers[kk] = vv

    title = _coerce_header_value(rendered_dict.get("title"))
    if title is not None:
        headers.setdefault("Title", title)
    elif message.get("title"):
        headers.setdefault("Title", message["title"])

    tags = rendered_dict.get("tags")
    if isinstance(tags, list):
        joined = ",".join(str(x).strip() for x in tags if str(x).strip())
        if joined:
            headers.setdefault("Tags", joined)
    else:
        t = _coerce_header_value(tags)
        if t is not None:
            headers.setdefault("Tags", t)
        elif isinstance(message.get("tags_json"), list) and message.get("tags_json"):
            joined = ",".join(
                str(x).strip() for x in message["tags_json"] if str(x).strip()
            )
            if joined:
                headers.setdefault("Tags", joined)

    _PRIORITY_MAP = {1: "min", 2: "low", 3: "default", 4: "high", 5: "urgent"}
    prio = _coerce_header_value(rendered_dict.get("priority"))
    if prio is not None:
        headers.setdefault("Priority", prio)
    elif message.get("priority") and message.get("priority") != 3:
        ntfy_prio = _PRIORITY_MAP.get(message["priority"])
        if ntfy_prio:
            headers.setdefault("Priority", ntfy_prio)

    click = _coerce_header_value(rendered_dict.get("click"))
    if click is not None:
        headers.setdefault("Click", click)

    icon = _coerce_header_value(rendered_dict.get("icon"))
    if icon is not None:
        headers.setdefault("Icon", icon)

    attach = _coerce_header_value(rendered_dict.get("attach"))
    if attach is not None:
        headers.setdefault("Attach", attach)

    markdown = rendered_dict.get("markdown")
    if isinstance(markdown, bool) and markdown:
        headers.setdefault("Markdown", "true")

    token = str(channel_config.get("access_token") or "").strip()
    if token:
        headers.setdefault("Authorization", f"Bearer {token}")

    username = str(channel_config.get("username") or "").strip()
    password = str(channel_config.get("password") or "").strip()
    auth = (username, password) if username and password and not token else None

    return url, body.encode("utf-8"), headers, auth


async def send_ntfy_publish(
    *,
    url: str,
    body: bytes,
    headers: dict[str, str],
    auth: tuple[str, str] | None,
    timeout: float = 5.0,
) -> tuple[bool, dict]:
    """Send ntfy notification via async HTTP."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url, content=body, headers=headers, timeout=timeout, auth=auth
        )

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
