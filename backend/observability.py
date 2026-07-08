"""Shared Sentry initialization for API and worker processes."""

from __future__ import annotations

from .config import get_settings


def init_sentry(*, extra_integrations: tuple = ()) -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=list(extra_integrations),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.sentry_environment,
    )
