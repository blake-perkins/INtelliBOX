"""Tests for file watcher resilience and health monitoring."""

import threading
import time
from pathlib import Path
from unittest.mock import patch


class TestWatchInbox:
    """Tests for the watch_inbox polling function."""

    def test_processes_new_eml_files(self, tmp_path):
        """Dropping a .eml file in the inbox dir triggers the callback."""
        from emailtools.ingestion.file_watcher import watch_inbox

        # Create a fake .eml file
        eml_file = tmp_path / "test_email.eml"
        eml_file.write_text("Subject: Test\n\nBody")

        processed = []

        def callback(path):
            processed.append(path)

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, callback, run_once=True)

        assert len(processed) == 1
        assert processed[0].name == "test_email.eml"

    def test_processes_msg_files(self, tmp_path):
        """Dropping a .msg file in the inbox dir triggers the callback."""
        from emailtools.ingestion.file_watcher import watch_inbox

        msg_file = tmp_path / "test_email.msg"
        msg_file.write_bytes(b"\x00" * 10)

        processed = []

        def callback(path):
            processed.append(path)

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, callback, run_once=True)

        assert len(processed) == 1
        assert processed[0].name == "test_email.msg"

    def test_creates_missing_dir(self, tmp_path):
        """If inbox dir doesn't exist, watch_inbox creates it."""
        from emailtools.ingestion.file_watcher import watch_inbox

        missing_dir = tmp_path / "nonexistent" / "inbox"
        assert not missing_dir.exists()

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(missing_dir, lambda p: None, run_once=True)

        assert missing_dir.exists()

    def test_handles_callback_error(self, tmp_path):
        """If callback raises, file is marked processed (no crash, no retry loop)."""
        from emailtools.ingestion.file_watcher import watch_inbox

        eml_file = tmp_path / "bad_email.eml"
        eml_file.write_text("Subject: Bad\n\nBody")

        def bad_callback(path):
            raise ValueError("parse error")

        # Should not raise
        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, bad_callback, run_once=True)

    def test_no_retry_on_failed_files(self, tmp_path):
        """Failed files are not reprocessed on subsequent polls."""

        eml_file = tmp_path / "retry_test.eml"
        eml_file.write_text("Subject: Retry\n\nBody")

        call_count = 0
        poll_count = 0

        def counting_callback(path):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always fails")

        # We need a custom run that does 2 polls then stops.
        # Patch watch_inbox to run a few iterations manually.
        # Instead, let's test the processed_files set directly.
        # Use run_once=True twice by resetting the watcher state.

        # Actually, let's test this by running the watcher in a thread
        # for a brief period and checking call_count.
        stop_event = threading.Event()

        def limited_watch():
            """Run watch_inbox but interrupt after a short delay."""
            import emailtools.ingestion.file_watcher as fw
            original_sleep = time.sleep

            def short_sleep(secs):
                nonlocal poll_count
                poll_count += 1
                if poll_count >= 2:
                    raise KeyboardInterrupt()
                original_sleep(0.01)  # fast poll

            with patch("emailtools.ingestion.file_watcher.SettingsService"):
                with patch("time.sleep", side_effect=short_sleep):
                    fw.watch_inbox(tmp_path, counting_callback, interval=1)

        limited_watch()

        # Callback should only be called once (first poll), not again on second poll
        assert call_count == 1

    def test_empty_inbox(self, tmp_path):
        """Empty inbox directory processes without error."""
        from emailtools.ingestion.file_watcher import watch_inbox

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: None, run_once=True)

    def test_multiple_files_processed(self, tmp_path):
        """Multiple .eml files are all processed in one pass."""
        from emailtools.ingestion.file_watcher import watch_inbox

        for i in range(5):
            (tmp_path / f"email_{i}.eml").write_text(f"Subject: Test {i}\n\n")

        processed = []

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: processed.append(p), run_once=True)

        assert len(processed) == 5


class TestWatcherHealth:
    """Tests for the watcher health monitoring system."""

    def test_health_initial_state(self):
        """Health starts as not alive with zero counters."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health

        _reset_health()
        health = get_watcher_health()

        assert health["is_alive"] is False
        assert health["files_processed"] == 0
        assert health["error_count"] == 0
        assert health["last_poll_at"] is None

    def test_health_reports_alive_after_poll(self, tmp_path):
        """After a successful poll, health reports is_alive=True."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: None, run_once=True)

        health = get_watcher_health()
        assert health["is_alive"] is True
        assert health["last_poll_at"] is not None

    def test_health_tracks_files_processed(self, tmp_path):
        """Health counter increments for each successfully processed file."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        for i in range(3):
            (tmp_path / f"email_{i}.eml").write_text(f"Subject: {i}\n\n")

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: None, run_once=True)

        health = get_watcher_health()
        assert health["files_processed"] == 3

    def test_health_tracks_error_count(self, tmp_path):
        """Health error_count increments when callback raises."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        (tmp_path / "bad1.eml").write_text("bad")
        (tmp_path / "bad2.eml").write_text("bad")

        def bad_callback(path):
            raise ValueError("parse error")

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, bad_callback, run_once=True)

        health = get_watcher_health()
        assert health["error_count"] == 2
        # Files still counted as processed (to avoid retry loop)
        assert health["files_processed"] == 0  # Only successful ones count

    def test_health_mixed_success_and_error(self, tmp_path):
        """Health correctly tracks mix of successes and failures."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        (tmp_path / "good1.eml").write_text("good")
        (tmp_path / "bad1.eml").write_text("bad")
        (tmp_path / "good2.eml").write_text("good")

        def selective_callback(path):
            if "bad" in path.name:
                raise ValueError("parse error")

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, selective_callback, run_once=True)

        health = get_watcher_health()
        assert health["files_processed"] == 2
        assert health["error_count"] == 1

    def test_health_returns_dict(self):
        """get_watcher_health returns a plain dict (safe for JSON serialization)."""
        from emailtools.ingestion.file_watcher import get_watcher_health

        health = get_watcher_health()
        assert isinstance(health, dict)
        assert "is_alive" in health
        assert "files_processed" in health
        assert "error_count" in health
        assert "last_poll_at" in health


class TestSupervisedWatcher:
    """Tests for the supervised watcher restart logic."""

    def test_supervised_watcher_restarts_on_crash(self):
        """Supervised watcher retries after crash up to max_restarts."""
        from emailtools.ingestion.file_watcher import supervised_watch

        call_count = 0

        def crashing_watch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("watcher crash")

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=crashing_watch):
            with patch("time.sleep"):  # skip backoff delay
                supervised_watch(
                    inbox_dir=Path("data/inbox"),
                    callback=lambda p: None,
                    max_restarts=3,
                )

        # Initial run + 3 restarts = 4 total attempts
        assert call_count == 4

    def test_supervised_watcher_stops_on_keyboard_interrupt(self):
        """KeyboardInterrupt is not retried."""
        from emailtools.ingestion.file_watcher import supervised_watch

        call_count = 0

        def keyboard_watch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise KeyboardInterrupt()

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=keyboard_watch):
            supervised_watch(
                inbox_dir=Path("data/inbox"),
                callback=lambda p: None,
                max_restarts=3,
            )

        assert call_count == 1  # No restarts on KeyboardInterrupt

    def test_supervised_watcher_exponential_backoff(self):
        """Backoff delays increase with each restart attempt."""
        from emailtools.ingestion.file_watcher import supervised_watch

        sleep_calls = []

        def crashing_watch(*args, **kwargs):
            raise RuntimeError("crash")

        def mock_sleep(secs):
            sleep_calls.append(secs)

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=crashing_watch):
            with patch("time.sleep", side_effect=mock_sleep):
                supervised_watch(
                    inbox_dir=Path("data/inbox"),
                    callback=lambda p: None,
                    max_restarts=3,
                )

        # Should have 3 sleep calls (after each failed attempt except the last)
        assert len(sleep_calls) == 3
        # Backoff should increase: 5, 10, 15 (capped at 30)
        assert sleep_calls[0] < sleep_calls[1]
        assert sleep_calls[1] < sleep_calls[2]

    def test_supervised_watcher_exact_backoff_values(self):
        """Verify exact backoff: min(30, 5*(attempt+1)) = 5, 10, 15, 20, 25."""
        from emailtools.ingestion.file_watcher import supervised_watch

        sleep_calls = []

        def crashing_watch(*args, **kwargs):
            raise RuntimeError("crash")

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=crashing_watch):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                supervised_watch(
                    inbox_dir=Path("data/inbox"),
                    callback=lambda p: None,
                    max_restarts=5,
                )

        assert sleep_calls == [5, 10, 15, 20, 25]

    def test_supervised_watcher_backoff_capped_at_30(self):
        """Backoff is capped at 30 seconds even with many restarts."""
        from emailtools.ingestion.file_watcher import supervised_watch

        sleep_calls = []

        def crashing_watch(*args, **kwargs):
            raise RuntimeError("crash")

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=crashing_watch):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                supervised_watch(
                    inbox_dir=Path("data/inbox"),
                    callback=lambda p: None,
                    max_restarts=8,
                )

        # 5, 10, 15, 20, 25, 30, 30, 30
        assert all(s <= 30 for s in sleep_calls)
        assert sleep_calls[-1] == 30

    def test_supervised_total_backoff_time(self):
        """Total backoff time for max_restarts=3 is 5+10+15 = 30 seconds."""
        from emailtools.ingestion.file_watcher import supervised_watch

        sleep_calls = []

        def crashing_watch(*args, **kwargs):
            raise RuntimeError("crash")

        with patch("emailtools.ingestion.file_watcher.watch_inbox", side_effect=crashing_watch):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                supervised_watch(
                    inbox_dir=Path("data/inbox"),
                    callback=lambda p: None,
                    max_restarts=3,
                )

        assert sum(sleep_calls) == 30  # 5 + 10 + 15


class TestWatcherHealthAccumulation:
    """Tests verifying health counters accumulate correctly over time."""

    def test_health_accumulates_across_multiple_polls(self, tmp_path):
        """Health counters accumulate across multiple poll cycles."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        # First poll: 2 files
        (tmp_path / "a.eml").write_text("a")
        (tmp_path / "b.eml").write_text("b")

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: None, run_once=True)

        health1 = get_watcher_health()
        assert health1["files_processed"] == 2

        # Second poll: 1 more file (previous 2 already in processed_files set)
        # Since run_once=True creates a fresh processed_files set each time,
        # the health counter should accumulate
        (tmp_path / "c.eml").write_text("c")

        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, lambda p: None, run_once=True)

        health2 = get_watcher_health()
        # Second run sees a, b, c (3 files) since processed_files is fresh
        assert health2["files_processed"] == 5  # 2 + 3

    def test_health_error_count_accumulates(self, tmp_path):
        """Error count persists and accumulates across runs."""
        from emailtools.ingestion.file_watcher import _reset_health, get_watcher_health, watch_inbox

        _reset_health()

        def always_fail(path):
            raise ValueError("fail")

        # First run: 1 error
        (tmp_path / "err1.eml").write_text("e")
        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, always_fail, run_once=True)

        assert get_watcher_health()["error_count"] == 1

        # Second run: 2 more errors (err1 reprocessed + err2)
        (tmp_path / "err2.eml").write_text("e")
        with patch("emailtools.ingestion.file_watcher.SettingsService"):
            watch_inbox(tmp_path, always_fail, run_once=True)

        assert get_watcher_health()["error_count"] == 3  # 1 + 2
