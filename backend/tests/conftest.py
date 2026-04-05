from __future__ import annotations

import pytest

from backend.config import get_settings

TEST_DATABASE_URL = "postgresql://herald:herald@127.0.0.1:5432/herald"
TEST_JWT_SIGNING_KEY = "test-jwt-signing-key-0123456789abcdef"
TEST_SECRET_KEY = "test-secret-key-0123456789abcdef"
TEST_ENCRYPTION_KEY = "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc="


@pytest.fixture(autouse=True)
def configure_backend_test_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("DJANGO_SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("JWT_SIGNING_KEY", TEST_JWT_SIGNING_KEY)
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
