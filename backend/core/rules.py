import re

# Framework-agnostic rule matching logic
# Accepts dict representations instead of Django models


def rule_matches_message(filter_json: dict, message: dict) -> bool:
    """Check if message matches rule filter."""
    f = filter_json or {}

    ingest_ids = f.get("ingest_endpoint_ids")
    if ingest_ids is not None:
        if str(message.get("ingest_endpoint_id")) not in {str(x) for x in ingest_ids}:
            return False

    body_filter = f.get("body") or {}
    contains = body_filter.get("contains")
    if contains is not None:
        hay = (message.get("body") or "").lower()
        needles = [str(s).lower() for s in contains if str(s).strip()]
        if needles and not any(n in hay for n in needles):
            return False

    regex = body_filter.get("regex")
    if regex is not None and str(regex).strip():
        try:
            pat = re.compile(str(regex), flags=re.IGNORECASE)
        except re.error:
            return False
        if pat.search(message.get("body") or "") is None:
            return False

    priority_filter = f.get("priority") or {}
    pmin = priority_filter.get("min")
    if pmin is not None:
        try:
            if message.get("priority", 3) < int(pmin):
                return False
        except (ValueError, TypeError):
            pass
    pmax = priority_filter.get("max")
    if pmax is not None:
        try:
            if message.get("priority", 3) > int(pmax):
                return False
        except (ValueError, TypeError):
            pass

    tags_filter = f.get("tags")
    if tags_filter is not None and isinstance(tags_filter, list) and tags_filter:
        msg_tags = set()
        if isinstance(message.get("tags_json"), list):
            msg_tags = {str(t).lower() for t in message.get("tags_json", [])}
        filter_tags = {str(t).lower() for t in tags_filter}
        if not msg_tags & filter_tags:
            return False

    group_filter = f.get("group")
    if group_filter is not None:
        if (message.get("group") or "") != str(group_filter):
            return False

    return True
