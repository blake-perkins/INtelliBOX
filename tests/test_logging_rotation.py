"""Tests for log rotation configuration and structured logging."""

import json as json_mod
import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path


def test_file_handler_created():
    """setup_logging creates a RotatingFileHandler when log_dir is writable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Clear any existing handlers on a fresh logger name
        logger_name = "test_rotation_file"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        from intellibox.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)

        handler_types = [type(h) for h in result.handlers]
        assert RotatingFileHandler in handler_types

        # Cleanup
        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_console_handler_still_present():
    """setup_logging still includes a StreamHandler for console output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger_name = "test_rotation_console"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        from intellibox.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)

        handler_types = [type(h) for h in result.handlers]
        assert logging.StreamHandler in handler_types or any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            for h in result.handlers
        )

        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_log_file_created():
    """setup_logging creates the actual log file on disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger_name = "test_rotation_exists"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        from intellibox.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)
        result.info("test message")

        log_file = Path(tmpdir) / "intellibox.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "test message" in content

        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_rotation_creates_backup():
    """Writing enough data triggers rotation and creates backup files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger_name = "test_rotation_backup"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        from intellibox.utils.logging import setup_logging
        # Use a very small maxBytes to trigger rotation quickly
        result = setup_logging(name=logger_name, log_dir=tmpdir, max_bytes=1000, backup_count=3)

        # Write enough data to trigger rotation
        for i in range(200):
            result.info(f"log message number {i} with some padding to fill bytes quickly xxxx")

        log_file = Path(tmpdir) / "intellibox.log"
        backup_file = Path(tmpdir) / "intellibox.log.1"
        assert log_file.exists()
        assert backup_file.exists(), "Rotation should have created at least one backup file"

        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_unwritable_dir_does_not_crash():
    """If log_dir is unwritable, setup_logging still returns a working logger."""
    logger_name = "test_rotation_unwritable"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    from intellibox.utils.logging import setup_logging
    # Use a path that doesn't exist and can't be created
    result = setup_logging(name=logger_name, log_dir="/nonexistent/path/that/cannot/exist")

    # Should still have at least the console handler
    assert len(result.handlers) >= 1
    # Should be usable without error
    result.info("this should not crash")

    for h in result.handlers[:]:
        h.close()
        result.removeHandler(h)


def test_json_format_produces_valid_json(monkeypatch):
    """When LOG_FORMAT=json, log output is valid JSON with expected keys."""
    monkeypatch.setattr("intellibox.config.settings.log_format", "json")

    logger_name = "test_json_format"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    with tempfile.TemporaryDirectory() as tmpdir:
        from intellibox.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)
        result.info("test json message")

        log_file = Path(tmpdir) / "intellibox.log"
        content = log_file.read_text().strip()
        for line in content.splitlines():
            parsed = json_mod.loads(line)
            assert parsed["message"] == "test json message"
            assert "timestamp" in parsed
            assert "level" in parsed
            assert parsed["level"] == "INFO"

        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_text_format_unchanged(monkeypatch):
    """When LOG_FORMAT=text (default), output matches the existing plain-text format."""
    monkeypatch.setattr("intellibox.config.settings.log_format", "text")

    logger_name = "test_text_format"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()

    with tempfile.TemporaryDirectory() as tmpdir:
        from intellibox.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)
        result.info("plain text check")

        log_file = Path(tmpdir) / "intellibox.log"
        content = log_file.read_text().strip()
        assert " - test_text_format - INFO - plain text check" in content

        for h in result.handlers[:]:
            h.close()
            result.removeHandler(h)


def test_sentry_not_initialized_when_dsn_empty(monkeypatch):
    """Sentry SDK should NOT be imported when SENTRY_DSN is empty."""
    import sys

    monkeypatch.setattr("intellibox.config.settings.sentry_dsn", "")

    # Save and remove sentry_sdk from sys.modules if already imported
    sentry_modules = [k for k in sys.modules if k.startswith("sentry_sdk")]
    saved = {k: sys.modules.pop(k) for k in sentry_modules}

    try:
        from intellibox.web.app import _init_sentry
        _init_sentry()
        assert "sentry_sdk" not in sys.modules
    finally:
        sys.modules.update(saved)


def test_sentry_initialized_when_dsn_set(monkeypatch):
    """Sentry SDK should be initialized when SENTRY_DSN is set."""
    monkeypatch.setattr("intellibox.config.settings.sentry_dsn", "https://examplePublicKey@o0.ingest.sentry.io/0")
    monkeypatch.setattr("intellibox.config.settings.sentry_environment", "test")
    monkeypatch.setattr("intellibox.config.settings.sentry_traces_sample_rate", 0.0)

    from intellibox.web.app import _init_sentry
    _init_sentry()

    import sentry_sdk
    client = sentry_sdk.get_client()
    assert client.dsn is not None
