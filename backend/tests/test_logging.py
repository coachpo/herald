from __future__ import annotations

import json
import logging

import pytest
import structlog

from backend.config import get_settings
from backend.logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_logging_state():
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    structlog.reset_defaults()
    get_settings.cache_clear()
    root_logger.handlers.clear()

    try:
        yield
    finally:
        structlog.reset_defaults()
        get_settings.cache_clear()
        root_logger.handlers.clear()
        for handler in original_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


def _get_processor_formatter() -> structlog.stdlib.ProcessorFormatter:
    root_logger = logging.getLogger()

    assert len(root_logger.handlers) == 1

    formatter = root_logger.handlers[0].formatter
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    return formatter


def test_setup_logging_configures_structlog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("LOG_FORMAT", "json")
    get_settings.cache_clear()

    setup_logging()

    assert structlog.is_configured() is True

    config = structlog.get_config()
    assert isinstance(config["logger_factory"], structlog.stdlib.LoggerFactory)
    assert config["wrapper_class"] is structlog.stdlib.BoundLogger
    assert (
        config["processors"][-1]
        is structlog.stdlib.ProcessorFormatter.wrap_for_formatter
    )

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
    assert len(root_logger.handlers) == 1


def test_setup_logging_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_output=True)

    formatter = _get_processor_formatter()
    assert isinstance(formatter.processors[-1], structlog.processors.JSONRenderer)

    structlog.get_logger("test.json").info("json_output_enabled", answer=42)
    output = capsys.readouterr().err.strip()

    payload = json.loads(output)
    assert payload["event"] == "json_output_enabled"
    assert payload["answer"] == 42
    assert payload["logger"] == "test.json"


def test_setup_logging_console_output(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_output=False)

    formatter = _get_processor_formatter()
    assert isinstance(formatter.processors[-1], structlog.dev.ConsoleRenderer)

    structlog.get_logger("test.console").info("console_output_enabled", answer=42)
    output = capsys.readouterr().err.strip()

    assert "console_output_enabled" in output
    assert "answer" in output
    assert "42" in output


def test_stdlib_logger_uses_structlog(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(json_output=True)

    logger = logging.getLogger("backend.worker")
    logger.info("delivery_sent", extra={"delivery_id": "abc-123", "attempt_count": 2})

    output = capsys.readouterr().err.strip()
    payload = json.loads(output)

    assert payload["event"] == "delivery_sent"
    assert payload["logger"] == "backend.worker"
    assert payload["level"] == "info"
    assert payload["delivery_id"] == "abc-123"
    assert payload["attempt_count"] == 2
