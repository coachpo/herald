import re
from collections.abc import Mapping
from datetime import datetime

# Framework-agnostic template rendering
# Accepts dict representations instead of Django models


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}")


def _iso(dt: datetime | str | None) -> str | None:
    """Convert datetime to ISO format."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()

def _lookup(path: str, ctx: Mapping[str, object]) -> object | None:
    cur: object | None = ctx
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(part)
    return cur


def _render_str(s: str, ctx: Mapping[str, object]) -> str:
    def repl(m: re.Match[str]) -> str:
        val = _lookup(m.group(1), ctx)
        return "" if val is None else str(val)

    return _VAR_RE.sub(repl, s)


def render_template(value: object, ctx: Mapping[str, object]) -> object:
    if isinstance(value, str):
        return _render_str(value, ctx)
    if isinstance(value, list):
        return [render_template(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: render_template(v, ctx) for k, v in value.items()}
    return value


def build_template_context(message: dict, ingest_endpoint: dict) -> dict[str, object]:
    """Build template context from message and endpoint dicts."""
    tags = message.get("tags_json", []) if isinstance(message.get("tags_json"), list) else []
    extras = message.get("extras_json", {}) if isinstance(message.get("extras_json"), dict) else {}

    return {
        "message": {
            "id": str(message.get("id", "")),
            "received_at": _iso(message.get("received_at")),
            "title": message.get("title") or "",
            "body": message.get("body") or "",
            "group": message.get("group") or "",
            "priority": str(message.get("priority", 3)),
            "tags": ",".join(str(t) for t in tags),
            "url": message.get("url") or "",
            "extras": {str(k): str(v) for k, v in extras.items()},
        },
        "request": {
            "content_type": message.get("content_type") or "",
            "remote_ip": message.get("remote_ip") or "",
            "user_agent": message.get("user_agent") or "",
            "headers": message.get("headers_json", {})
            if isinstance(message.get("headers_json"), dict)
            else {},
            "query": message.get("query_json", {})
            if isinstance(message.get("query_json"), dict)
            else {},
        },
        "ingest_endpoint": {
            "id": str(ingest_endpoint.get("id", "")),
            "name": ingest_endpoint.get("name", ""),
        },
    }
