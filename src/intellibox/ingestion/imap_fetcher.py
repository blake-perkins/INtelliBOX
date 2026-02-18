"""IMAP email fetcher for polling a remote mailbox."""

import email
import imaplib
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from intellibox.utils.datetime_utils import utcnow
from intellibox.utils.logging import logger

# ── Health monitoring ────────────────────────────────────────────────────────

@dataclass
class IMAPHealth:
    """Tracks runtime health of the IMAP fetcher."""
    is_alive: bool = False
    last_poll_at: Optional[object] = None  # datetime
    error_count: int = 0
    emails_fetched: int = 0


_health = IMAPHealth()
_health_lock = threading.Lock()


def get_imap_health() -> dict:
    """Return a snapshot of IMAP fetcher health as a plain dict."""
    with _health_lock:
        return {
            "is_alive": _health.is_alive,
            "last_poll_at": _health.last_poll_at.isoformat() if _health.last_poll_at else None,
            "error_count": _health.error_count,
            "emails_fetched": _health.emails_fetched,
        }


def _reset_health() -> None:
    """Reset health counters (used by tests)."""
    with _health_lock:
        _health.is_alive = False
        _health.last_poll_at = None
        _health.error_count = 0
        _health.emails_fetched = 0


# ── Core fetcher ─────────────────────────────────────────────────────────────

def fetch_imap(
    host: str,
    port: int,
    user: str,
    password: str,
    inbox_dir: Path,
    use_ssl: bool = True,
    folder: str = "INBOX",
    interval: int = 60,
    run_once: bool = False,
) -> None:
    """
    Poll an IMAP mailbox for unseen emails and save them as .eml files.

    Downloaded emails are saved to inbox_dir where the file watcher
    picks them up for processing. Emails are marked as SEEN on the
    server after download so they aren't fetched again.

    Args:
        host: IMAP server hostname (e.g. outlook.office365.com)
        port: IMAP server port (typically 993 for SSL)
        user: IMAP username / email address
        password: IMAP password or app password
        inbox_dir: Path to save .eml files (data/inbox)
        use_ssl: Whether to use SSL (default True)
        folder: IMAP folder to poll (default INBOX)
        interval: Polling interval in seconds (default 60)
        run_once: If True, fetch once and exit
    """
    inbox_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"IMAP fetcher started: {user}@{host}:{port}/{folder} (poll every {interval}s)")

    try:
        while True:
            try:
                _poll_once(host, port, user, password, inbox_dir, use_ssl, folder)
            except (imaplib.IMAP4.error, OSError) as e:
                logger.error(f"IMAP poll error: {e}")
                with _health_lock:
                    _health.error_count += 1

            with _health_lock:
                _health.is_alive = True
                _health.last_poll_at = utcnow()

            if run_once:
                logger.info("IMAP single fetch complete, exiting")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("IMAP fetcher stopped by user")
    except Exception as e:
        logger.error(f"IMAP fetcher error: {e}")
        raise


def _poll_once(
    host: str,
    port: int,
    user: str,
    password: str,
    inbox_dir: Path,
    use_ssl: bool,
    folder: str,
) -> None:
    """Connect to IMAP, fetch unseen emails, save as .eml files."""
    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)

    try:
        conn.login(user, password)
        conn.select(folder)

        # Search for unseen (unread) messages
        status, data = conn.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            return

        msg_ids = data[0].split()
        logger.info(f"IMAP: found {len(msg_ids)} unseen email(s)")

        for msg_id in msg_ids:
            try:
                status, msg_data = conn.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Generate a safe filename from message-id or timestamp
                message_id = msg.get("Message-ID", "")
                if message_id:
                    # Strip < > and sanitize for filesystem
                    safe_id = message_id.strip("<>").replace("/", "_").replace("\\", "_")[:80]
                else:
                    safe_id = f"imap-{utcnow().strftime('%Y%m%d%H%M%S')}-{msg_id.decode()}"

                filename = f"{safe_id}.eml"
                filepath = inbox_dir / filename

                # Skip if already downloaded (shouldn't happen with UNSEEN, but be safe)
                if filepath.exists():
                    continue

                filepath.write_bytes(raw_email)
                logger.info(f"IMAP: saved {filename}")

                # Mark as seen so we don't fetch it again
                conn.store(msg_id, "+FLAGS", "\\Seen")

                with _health_lock:
                    _health.emails_fetched += 1

            except Exception as e:
                logger.error(f"IMAP: error fetching message {msg_id}: {e}")
                with _health_lock:
                    _health.error_count += 1

    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()


# ── Supervised fetcher ───────────────────────────────────────────────────────

def supervised_imap_fetch(
    host: str,
    port: int,
    user: str,
    password: str,
    inbox_dir: Path,
    use_ssl: bool = True,
    folder: str = "INBOX",
    interval: int = 60,
    max_restarts: int = 5,
) -> None:
    """Run fetch_imap with automatic restarts on crash."""
    for attempt in range(max_restarts + 1):
        try:
            fetch_imap(
                host, port, user, password, inbox_dir,
                use_ssl=use_ssl, folder=folder, interval=interval,
            )
            break
        except KeyboardInterrupt:
            logger.info("Supervised IMAP fetcher stopped by user")
            break
        except Exception as e:
            if attempt < max_restarts:
                wait = min(30, 5 * (attempt + 1))
                logger.error(
                    f"IMAP fetcher crashed (attempt {attempt + 1}/{max_restarts + 1}), "
                    f"restarting in {wait}s: {e}"
                )
                time.sleep(wait)
            else:
                logger.error(
                    f"IMAP fetcher crashed {max_restarts + 1} times, giving up: {e}"
                )
