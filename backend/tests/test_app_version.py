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


def test_get_app_version_falls_back_to_repo_version(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_VERSION", raising=False)

    def missing_package(_: str) -> str:
        raise PackageNotFoundError()

    monkeypatch.setattr(app_module, "package_version", missing_package)
    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "ROOT_VERSION_PATH", version_file)

    assert app_module._get_app_version() == "2.3.4"


def test_get_app_version_returns_unknown_when_repo_version_is_unavailable(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("APP_VERSION", raising=False)

    def missing_package(_: str) -> str:
        raise PackageNotFoundError()

    monkeypatch.setattr(app_module, "package_version", missing_package)
    monkeypatch.setattr(app_module, "ROOT_VERSION_PATH", tmp_path / "missing-VERSION")

    assert app_module._get_app_version() == "unknown"
