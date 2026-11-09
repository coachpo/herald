"""The four supported destinations share only this dispatch boundary."""
from __future__ import annotations
import asyncio
from .core.ssrf import SSRFError
from .providers import bark, gotify, mqtt, ntfy
from .providers.errors import DeliveryError

async def dispatch(kind: str, config: dict, message: dict, *, timeout: float) -> dict:
    adapters = {"bark": bark.send, "ntfy": ntfy.send, "gotify": gotify.send, "mqtt": mqtt.send}
    adapter = adapters.get(kind)
    if adapter is None:
        raise DeliveryError("unsupported_target")
    try:
        async with asyncio.timeout(timeout):
            return await adapter(config, message, timeout=timeout)
    except TimeoutError:
        raise DeliveryError("timeout") from None
    except SSRFError:
        raise DeliveryError("destination_blocked") from None
    except DeliveryError:
        raise
    except Exception:
        # Exceptions can contain credential-bearing URLs or payloads.
        raise DeliveryError("transport_error") from None

__all__ = ["DeliveryError", "dispatch"]
