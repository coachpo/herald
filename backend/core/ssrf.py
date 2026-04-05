import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """SSRF protection error."""
    pass


def _is_blocked_ip(ip: str, *, block_private_networks: bool) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if addr.is_loopback or addr.is_link_local:
        return True
    if block_private_networks and addr.is_private:
        return True
    return False


def assert_host_ssrf_safe(host: str, *, block_private_networks: bool):
    if host in {"localhost"}:
        raise SSRFError("blocked_host")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SSRFError("unresolvable_host") from e

    for info in infos:
        ip = str(info[4][0])
        if _is_blocked_ip(ip, block_private_networks=block_private_networks):
            raise SSRFError("blocked_ip")


def assert_ssrf_safe(url: str, *, block_private_networks: bool = True):
    """Assert URL is safe from SSRF attacks."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SSRFError("invalid_url_scheme")
    if not parsed.hostname:
        raise SSRFError("invalid_url_host")

    assert_host_ssrf_safe(parsed.hostname, block_private_networks=block_private_networks)
