from __future__ import annotations
import asyncio
import httpx
from ..core.ssrf import assert_ssrf_safe
from .errors import DeliveryError

async def post(url: str, *, timeout: float, **kwargs) -> dict:
    # A cancelled DNS lookup can never continue into post().
    await asyncio.to_thread(assert_ssrf_safe, url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.post(url, **kwargs)
    if not 200 <= response.status_code < 300:
        raise DeliveryError(f"http_{response.status_code}")
    # Response bodies and headers may echo secrets: do not persist them.
    return {"http_status": response.status_code}
