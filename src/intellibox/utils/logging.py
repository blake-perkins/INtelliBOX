"""Logging configuration for INtelliBOX."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from intellibox.config import settings


def _build_formatter() -> logging.Formatter:
    """Build the log formatter based on LOG_FORMAT setting."""
    if settings.log_format.lower() == "json":
        from pythonjsonlogger import jsonlogger

        return jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    return logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_logging(
    name: Optional[str] = None,
    log_dir: str = "data/logs",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Setup and configure logger with appropriate level and format.

    Args:
        name: Logger name (defaults to "intellibox")
        log_dir: Directory for log files (created if missing)
        max_bytes: Max size per log file before rotation (default 5 MB)
        backup_count: Number of rotated backups to keep (default 5)

    Returns:
        Configured logger instance
    """
    logger_name = name or "intellibox"
    logger = logging.getLogger(logger_name)

    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        formatter = _build_formatter()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Rotating file handler
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path / "intellibox.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass  # Non-fatal — log dir may be unwritable in some environments

    return logger


# Create default logger instance
logger = setup_logging()
