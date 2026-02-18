"""Tests for log rotation configuration."""

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

        from emailtools.utils.logging import setup_logging
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

        from emailtools.utils.logging import setup_logging
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

        from emailtools.utils.logging import setup_logging
        result = setup_logging(name=logger_name, log_dir=tmpdir)
        result.info("test message")

        log_file = Path(tmpdir) / "emailtools.log"
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

        from emailtools.utils.logging import setup_logging
        # Use a very small maxBytes to trigger rotation quickly
        result = setup_logging(name=logger_name, log_dir=tmpdir, max_bytes=1000, backup_count=3)

        # Write enough data to trigger rotation
        for i in range(200):
            result.info(f"log message number {i} with some padding to fill bytes quickly xxxx")

        log_file = Path(tmpdir) / "emailtools.log"
        backup_file = Path(tmpdir) / "emailtools.log.1"
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

    from emailtools.utils.logging import setup_logging
    # Use a path that doesn't exist and can't be created
    result = setup_logging(name=logger_name, log_dir="/nonexistent/path/that/cannot/exist")

    # Should still have at least the console handler
    assert len(result.handlers) >= 1
    # Should be usable without error
    result.info("this should not crash")

    for h in result.handlers[:]:
        h.close()
        result.removeHandler(h)
