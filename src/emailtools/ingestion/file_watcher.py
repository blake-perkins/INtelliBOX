"""File watcher for monitoring the inbox directory."""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from emailtools.utils.datetime_utils import utcnow
from emailtools.utils.logging import logger
from emailtools.settings_service import SettingsService


# ── Health monitoring ────────────────────────────────────────────────────────

@dataclass
class WatcherHealth:
    """Tracks runtime health of the file watcher."""
    is_alive: bool = False
    last_poll_at: Optional[object] = None  # datetime
    error_count: int = 0
    files_processed: int = 0


_health = WatcherHealth()
_health_lock = threading.Lock()


def get_watcher_health() -> dict:
    """Return a snapshot of watcher health as a plain dict."""
    with _health_lock:
        return {
            "is_alive": _health.is_alive,
            "last_poll_at": _health.last_poll_at.isoformat() if _health.last_poll_at else None,
            "error_count": _health.error_count,
            "files_processed": _health.files_processed,
        }


def _reset_health() -> None:
    """Reset health counters (used by tests)."""
    with _health_lock:
        _health.is_alive = False
        _health.last_poll_at = None
        _health.error_count = 0
        _health.files_processed = 0


# ── Core watcher ─────────────────────────────────────────────────────────────

def watch_inbox(
    inbox_dir: Path,
    callback: Callable[[Path], None],
    interval: int = 5,
    run_once: bool = False
) -> None:
    """
    Watch the inbox directory for new .eml files and process them.

    Args:
        inbox_dir: Path to the inbox directory to monitor
        callback: Function to call when new .eml files are found
        interval: Polling interval in seconds (default: 5)
        run_once: If True, process existing files and exit (default: False)
    """
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created inbox directory: {inbox_dir}")

    logger.info(f"Watching inbox: {inbox_dir}")

    processed_files = set()

    try:
        while True:
            # Find all .eml and .msg files
            current_files = set(inbox_dir.glob("*.eml")) | set(inbox_dir.glob("*.msg"))

            # Identify new files
            new_files = current_files - processed_files

            if new_files:
                logger.info(f"Found {len(new_files)} new file(s)")
                for eml_file in new_files:
                    try:
                        logger.info(f"Processing: {eml_file.name}")
                        callback(eml_file)
                        processed_files.add(eml_file)
                        with _health_lock:
                            _health.files_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing {eml_file}: {e}")
                        # Mark as processed to avoid retry loop
                        processed_files.add(eml_file)
                        with _health_lock:
                            _health.error_count += 1

            # Update health after each poll
            with _health_lock:
                _health.is_alive = True
                _health.last_poll_at = utcnow()

            # Record this poll as the last sync time (even if no new files)
            try:
                SettingsService.update_last_sync_time()
            except Exception:
                pass

            if run_once:
                logger.info("Single run complete, exiting")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("File watcher stopped by user")
    except Exception as e:
        logger.error(f"File watcher error: {e}")
        raise


# ── Supervised watcher ───────────────────────────────────────────────────────

def supervised_watch(
    inbox_dir: Path,
    callback: Callable[[Path], None],
    interval: int = 5,
    max_restarts: int = 5,
) -> None:
    """Run watch_inbox with automatic restarts on crash.

    Args:
        inbox_dir: Path to the inbox directory to monitor
        callback: Function to call when new .eml files are found
        interval: Polling interval in seconds
        max_restarts: Maximum number of restart attempts before giving up
    """
    for attempt in range(max_restarts + 1):
        try:
            watch_inbox(inbox_dir, callback, interval=interval)
            break  # Clean exit (e.g. KeyboardInterrupt handled inside)
        except KeyboardInterrupt:
            logger.info("Supervised watcher stopped by user")
            break
        except Exception as e:
            if attempt < max_restarts:
                wait = min(30, 5 * (attempt + 1))
                logger.error(
                    f"Watcher crashed (attempt {attempt + 1}/{max_restarts + 1}), "
                    f"restarting in {wait}s: {e}"
                )
                time.sleep(wait)
            else:
                logger.error(
                    f"Watcher crashed {max_restarts + 1} times, giving up: {e}"
                )
