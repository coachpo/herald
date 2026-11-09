"""Destination checks shared by configuration validation and transports."""
import ipaddress
import socket
from urllib.parse import urlsplit

class SSRFError(ValueError):
    pass

def _is_blocked_ip(ip: str, *, block_private_networks: bool) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
        return True
    return block_private_networks and (address.is_private or address.is_reserved)

def assert_host_ssrf_safe(host: str, *, block_private_networks: bool):
    if not host or host.rstrip(".").lower() == "localhost":
        raise SSRFError("blocked_host")
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise SSRFError("unresolvable_host") from None
    if not addresses or any(_is_blocked_ip(str(info[4][0]), block_private_networks=block_private_networks) for info in addresses):
        raise SSRFError("blocked_ip")

def assert_ssrf_safe(url: str, *, block_private_networks: bool = True):
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise SSRFError("invalid_url")
        if parts.username is not None or parts.password is not None or parts.fragment or parts.query:
            raise SSRFError("invalid_url")
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise SSRFError("invalid_url")
    except ValueError:
        raise SSRFError("invalid_url") from None
    assert_host_ssrf_safe(parts.hostname, block_private_networks=block_private_networks)
