import pytest

from backend.config import get_settings


def _clear():
    get_settings.cache_clear()


def test_secret_key_env_var_renamed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    _clear()
    assert get_settings().secret_key == "s3cret-value-0123456789abcdef"
    _clear()


def test_production_rejects_default_secret_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _clear()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings()
    _clear()


def test_production_rejects_empty_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", "")
    _clear()
    with pytest.raises(RuntimeError, match="CHANNEL_CONFIG_ENCRYPTION_KEY"):
        get_settings()
    _clear()


def test_production_rejects_empty_jwt_key_via_fallback(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s3cret-value-0123456789abcdef")
    monkeypatch.setenv(
        "CHANNEL_CONFIG_ENCRYPTION_KEY",
        "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc=",
    )
    monkeypatch.setenv("JWT_SIGNING_KEY", "")
    _clear()
    assert get_settings().jwt_signing_key == "s3cret-value-0123456789abcdef"
    _clear()


def test_development_accepts_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _clear()
    assert get_settings().secret_key == "dev-insecure"
    _clear()


def test_production_rejects_change_me_template_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me-32-bytes-min")
    monkeypatch.setenv(
        "CHANNEL_CONFIG_ENCRYPTION_KEY",
        "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc=",
    )
    _clear()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings()
    _clear()
