from importlib.metadata import PackageNotFoundError

from backend import app as app_module


def test_get_app_version_prefers_env(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-override")
    monkeypatch.setattr(app_module, "package_version", lambda _: "9.9.9")

    assert app_module._get_app_version() == "test-override"


def test_get_app_version_uses_package_metadata(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.setattr(app_module, "package_version", lambda _: "1.2.3")

    assert app_module._get_app_version() == "1.2.3"


def test_get_app_version_falls_back_when_package_missing(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)

    def missing_package(_: str) -> str:
        raise PackageNotFoundError()

    monkeypatch.setattr(app_module, "package_version", missing_package)

    assert app_module._get_app_version() == "0.9.0"
