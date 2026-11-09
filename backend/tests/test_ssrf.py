import socket
import pytest
from backend.core.ssrf import SSRFError, assert_host_ssrf_safe, assert_ssrf_safe

def dns(monkeypatch, addresses):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in addresses])

@pytest.mark.parametrize("ip", ["127.0.0.1", "::1", "169.254.169.254", "fe80::1", "::ffff:127.0.0.1", "0.0.0.0", "224.0.0.1"])
@pytest.mark.parametrize("block_private", [True, False])
def test_loopback_linklocal_and_special_always_blocked(monkeypatch, ip, block_private):
    dns(monkeypatch, [ip])
    with pytest.raises(SSRFError):
        assert_host_ssrf_safe("destination.example", block_private_networks=block_private)

def test_all_resolved_addresses_are_checked(monkeypatch):
    dns(monkeypatch, ["8.8.8.8", "10.0.0.1"])
    with pytest.raises(SSRFError):
        assert_ssrf_safe("https://destination.example")

def test_public_destination_allowed(monkeypatch):
    dns(monkeypatch, ["8.8.8.8", "2606:4700:4700::1111"])
    assert_ssrf_safe("https://destination.example/prefix")

@pytest.mark.parametrize("url", ["file:///etc/passwd", "http:///missing", "http://localhost", "http://user:password@public.example", "https://public.example/?key=secret", "https://public.example/#fragment", "https://public.example:bad", "http://[malformed"])
def test_invalid_destination_rejected(monkeypatch, url):
    dns(monkeypatch, ["8.8.8.8"])
    with pytest.raises(SSRFError):
        assert_ssrf_safe(url)

def test_unresolvable_hostname_fails_closed(monkeypatch):
    def fail(*_a, **_k):
        raise socket.gaierror
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(SSRFError, match="unresolvable_host"):
        assert_ssrf_safe("https://destination.example")
