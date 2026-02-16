"""Logging configuration for EmailTools."""

import logging
import sys
from typing import Optional

from emailtools.config import settings


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """
    Setup and configure logger with appropriate level and format.

    Args:
        name: Logger name (defaults to "emailtools")

    Returns:
        Configured logger instance
    """
    logger_name = name or "emailtools"
    logger = logging.getLogger(logger_name)

    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


# Create default logger instance
logger = setup_logging()
