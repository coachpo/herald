"""Test core modules - rules, template, crypto, ssrf."""

import socket

import pytest

from backend.core.rules import rule_matches_message
from backend.core.template import build_template_context, render_template
from backend.config import get_settings
from backend.core.crypto import decrypt_json_bytes, encrypt_json_bytes
from backend.core import crypto as crypto_mod
from backend.core.ssrf import assert_ssrf_safe, SSRFError


class TestRules:
    """Test rule matching logic."""

    def test_empty_filter_matches_all(self):
        """Empty filter should match any message."""
        message = {"body": "test", "priority": 3}
        assert rule_matches_message({}, message) is True

    def test_body_filter_match(self):
        """Body filter should match substring."""
        message = {"body": "hello world", "priority": 3}
        assert rule_matches_message({"body": {"contains": ["world"]}}, message) is True
        assert rule_matches_message({"body": {"contains": ["missing"]}}, message) is False

    def test_priority_filter(self):
        """Priority filter should match exact value."""
        message = {"body": "test", "priority": 5}
        assert rule_matches_message({"priority": {"min": 5}}, message) is True
        assert rule_matches_message({"priority": {"max": 3}}, message) is False

    def test_tag_filter(self):
        """Tag filter should match if any tag matches."""
        message = {"body": "test", "tags_json": ["urgent", "alert"]}
        assert rule_matches_message({"tags": ["urgent"]}, message) is True
        assert rule_matches_message({"tags": ["missing"]}, message) is False

    def test_body_regex_filter(self):
        message = {"body": "Disk ALERT"}
        assert rule_matches_message({"body": {"regex": "disk\\s+alert"}}, message) is True
        assert rule_matches_message({"body": {"regex": "cpu"}}, message) is False

    def test_invalid_regex_rejects(self):
        assert rule_matches_message({"body": {"regex": "["}}, {"body": "x"}) is False

    def test_ingest_endpoint_ids_filter(self):
        message = {"body": "x", "ingest_endpoint_id": "ep1"}
        assert rule_matches_message({"ingest_endpoint_ids": ["ep1"]}, message) is True
        assert rule_matches_message({"ingest_endpoint_ids": ["ep2"]}, message) is False

    def test_group_filter(self):
        assert rule_matches_message({"group": "ops"}, {"body": "x", "group": "ops"}) is True
        assert rule_matches_message({"group": "ops"}, {"body": "x", "group": "dev"}) is False

    def test_combined_filters_are_and(self):
        filt = {"body": {"contains": ["alert"]}, "priority": {"min": 4}, "group": "ops"}
        assert rule_matches_message(filt, {"body": "alert", "priority": 4, "group": "ops"}) is True
        assert rule_matches_message(filt, {"body": "alert", "priority": 3, "group": "ops"}) is False

    def test_priority_defaults_to_three(self):
        assert rule_matches_message({"priority": {"min": 3}}, {"body": "x"}) is True
        assert rule_matches_message({"priority": {"min": 4}}, {"body": "x"}) is False


class TestTemplate:
    """Test template rendering."""

    def test_build_context(self):
        """Build template context from message and endpoint."""
        message = {"body": "test body", "title": "test title", "priority": 3}
        endpoint = {"name": "test-endpoint"}

        ctx = build_template_context(message, endpoint)

        assert ctx["message"]["body"] == "test body"
        assert ctx["message"]["title"] == "test title"
        assert ctx["ingest_endpoint"]["name"] == "test-endpoint"

    def test_render_simple_template(self):
        """Render simple mustache template."""
        template = {"body": "{{message.body}}", "title": "{{message.title}}"}
        context = {
            "message": {"body": "hello", "title": "world"},
            "ingest_endpoint": {"name": "test"},
        }

        result = render_template(template, context)

        assert result["body"] == "hello"
        assert result["title"] == "world"

    def test_render_missing_variable(self):
        """Missing variables should render as empty string."""
        template = {"body": "{{message.missing}}"}
        context = {"message": {"body": "test"}, "ingest_endpoint": {}}

        result = render_template(template, context)

        assert result["body"] == ""


class TestCrypto:
    """Test config encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt and decrypt should be reversible."""
        plaintext = '{"server": "https://example.com", "token": "secret"}'

        encrypted = encrypt_json_bytes(plaintext.encode("utf-8"))
        decrypted = decrypt_json_bytes(encrypted).decode("utf-8")

        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_decrypt_with_wrong_key_fails(self, monkeypatch):
        """Decrypting with wrong key should fail."""
        from cryptography.fernet import Fernet, InvalidToken

        token = encrypt_json_bytes(b'{"test": "data"}')
        monkeypatch.setenv(
            "CHANNEL_CONFIG_ENCRYPTION_KEY",
            Fernet.generate_key().decode(),
        )
        get_settings.cache_clear()
        crypto_mod._fernet_from_settings.cache_clear()
        try:
            with pytest.raises(InvalidToken):
                decrypt_json_bytes(token)
        finally:
            crypto_mod._fernet_from_settings.cache_clear()


class TestSSRF:
    """Test SSRF protection."""

    @pytest.fixture(autouse=True)
    def _dns(self, monkeypatch):
        original = socket.getaddrinfo

        def wrapped(host, *args, **kwargs):
            if host in {"example.com", "api.github.com"}:
                return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
            return original(host, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", wrapped)

    def test_public_url_allowed(self):
        """Public URLs should be allowed."""
        assert_ssrf_safe("https://example.com/path", block_private_networks=True)
        assert_ssrf_safe("https://api.github.com", block_private_networks=True)

    def test_private_ip_blocked(self):
        """Private IPs should be blocked when enabled."""
        with pytest.raises(SSRFError):
            assert_ssrf_safe("http://192.168.1.1", block_private_networks=True)

        with pytest.raises(SSRFError):
            assert_ssrf_safe("http://10.0.0.1", block_private_networks=True)

        with pytest.raises(SSRFError):
            assert_ssrf_safe("http://127.0.0.1", block_private_networks=True)

    def test_private_ip_allowed_when_disabled(self):
        """Private IPs should be allowed when protection disabled."""
        assert_ssrf_safe("http://192.168.1.1", block_private_networks=False)
        assert_ssrf_safe("http://10.0.0.1", block_private_networks=False)

    def test_localhost_blocked(self):
        """Localhost should be blocked."""
        with pytest.raises(SSRFError):
            assert_ssrf_safe("http://localhost", block_private_networks=True)

        with pytest.raises(SSRFError):
            assert_ssrf_safe("http://127.0.0.1", block_private_networks=True)

    def test_invalid_url_rejected(self):
        """Invalid URLs should be rejected."""
        with pytest.raises(SSRFError):
            assert_ssrf_safe("not-a-url", block_private_networks=True)

        with pytest.raises(SSRFError):
            assert_ssrf_safe("", block_private_networks=True)
