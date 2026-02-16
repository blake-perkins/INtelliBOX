"""File watcher for monitoring the inbox directory."""

import time
from pathlib import Path
from typing import Callable, Optional

from emailtools.utils.logging import logger


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
            # Find all .eml files
            current_files = set(inbox_dir.glob("*.eml"))

            # Identify new files
            new_files = current_files - processed_files

            if new_files:
                logger.info(f"Found {len(new_files)} new file(s)")
                for eml_file in new_files:
                    try:
                        logger.info(f"Processing: {eml_file.name}")
                        callback(eml_file)
                        processed_files.add(eml_file)
                    except Exception as e:
                        logger.error(f"Error processing {eml_file}: {e}")
                        # Mark as processed to avoid retry loop
                        processed_files.add(eml_file)

            if run_once:
                logger.info("Single run complete, exiting")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("File watcher stopped by user")
    except Exception as e:
        logger.error(f"File watcher error: {e}")
        raise
