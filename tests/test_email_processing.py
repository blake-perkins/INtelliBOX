"""
Integration tests for the high-volume email processing pipeline.

Tests cover:
  1. Duplicate email merging (same message-id from different senders)
  2. Chain stripping (quoted/forwarded content removed before AI)
  3. Batch processing with rate limiting
  4. Volume handling (many emails at once)

Uses generated .msg files (Outlook format) built by tests/msg_factory.py.
The factory constructs real OLE2/CFBF binary containers that are parsed
by extract_msg, exercising the actual production code path.
"""

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emailtools.models import Base, Email, Action, ProcessingLog
from emailtools.ingestion.parser import parse_and_store_email, process_inbox
from emailtools.ingestion.chain_stripper import strip_quoted_text
from emailtools.ai.processor import process_email_with_ai, process_unprocessed_emails

# Import the .msg file factory (lives in tests/ alongside this file)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from msg_factory import make_msg


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix="_email_processing.db", prefix="test_")
_TEST_DB_URL = f"sqlite:///{_test_db_path}"
_engine = create_engine(_TEST_DB_URL, pool_pre_ping=True)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def clean_database():
    """Recreate all tables before every test."""
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    yield


@pytest.fixture
def session():
    """Provide a fresh database session."""
    s = _SessionLocal()
    yield s
    s.close()


@pytest.fixture
def inbox_dir(tmp_path):
    """Create a temporary inbox directory and patch archive_eml_file."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    archive = tmp_path / "emails"
    archive.mkdir()

    original_archive = "emailtools.ingestion.parser.archive_eml_file"

    def _fake_archive(email_path: Path, message_id: str) -> str:
        safe = message_id.replace("<", "").replace(">", "").replace("/", "_")
        dest = archive / f"{safe}{email_path.suffix}"
        counter = 1
        while dest.exists():
            dest = archive / f"{safe}_{counter}{email_path.suffix}"
            counter += 1
        shutil.move(str(email_path), str(dest))
        return str(dest)

    with patch(original_archive, side_effect=_fake_archive):
        yield inbox


# ---------------------------------------------------------------------------
# 1. DUPLICATE MERGING TESTS
# ---------------------------------------------------------------------------

class TestDuplicateMerging:
    """Verify that duplicate .msg emails are merged rather than duplicated."""

    def test_first_msg_stored_normally(self, session, inbox_dir):
        """First instance of a .msg email is stored as a new record."""
        make_msg(
            inbox_dir / "email1.msg",
            message_id="<unique-001@outlook.local>",
            subject="First email",
            sender_email="alice@example.com",
            sender_name="Alice",
        )
        result = parse_and_store_email(inbox_dir / "email1.msg", session)

        assert result is not None
        assert result.message_id == "<unique-001@outlook.local>"
        assert result.from_address == "alice@example.com"
        assert result.also_received_from is None

    def test_duplicate_from_different_sender_merges(self, session, inbox_dir):
        """Second copy of the same .msg from a different sender merges."""
        msg_id = "<dup-001@outlook.local>"

        make_msg(inbox_dir / "email1.msg", message_id=msg_id, sender_email="alice@example.com", sender_name="Alice")
        result1 = parse_and_store_email(inbox_dir / "email1.msg", session)
        assert result1 is not None

        make_msg(inbox_dir / "email2.msg", message_id=msg_id, sender_email="bob@example.com", sender_name="Bob")
        result2 = parse_and_store_email(inbox_dir / "email2.msg", session)
        assert result2 is None  # Returns None because it's a merge

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        also = json.loads(stored.also_received_from)
        assert len(also) == 1
        assert also[0]["address"] == "bob@example.com"
        assert also[0]["name"] == "Bob"

    def test_duplicate_from_three_senders_merges_all(self, session, inbox_dir):
        """Three .msg copies from three senders → original + 2 in also_received_from."""
        msg_id = "<dup-003@outlook.local>"
        senders = [
            ("alice@example.com", "Alice"),
            ("bob@example.com", "Bob"),
            ("charlie@example.com", "Charlie"),
        ]
        for i, (addr, name) in enumerate(senders):
            make_msg(inbox_dir / f"email_{i}.msg", message_id=msg_id, sender_email=addr, sender_name=name)
            parse_and_store_email(inbox_dir / f"email_{i}.msg", session)

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        assert stored.from_address == "alice@example.com"
        also = json.loads(stored.also_received_from)
        assert len(also) == 2
        merged_addrs = {s["address"] for s in also}
        assert merged_addrs == {"bob@example.com", "charlie@example.com"}

    def test_duplicate_from_same_sender_no_double_merge(self, session, inbox_dir):
        """Same sender forwarding twice doesn't duplicate in also_received_from."""
        msg_id = "<dup-004@outlook.local>"

        make_msg(inbox_dir / "email1.msg", message_id=msg_id, sender_email="alice@example.com")
        parse_and_store_email(inbox_dir / "email1.msg", session)

        make_msg(inbox_dir / "email2.msg", message_id=msg_id, sender_email="alice@example.com")
        parse_and_store_email(inbox_dir / "email2.msg", session)

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        also = json.loads(stored.also_received_from or "[]")
        assert len(also) == 0

    def test_different_message_ids_stored_separately(self, session, inbox_dir):
        """Different message-ids → separate records, not merged."""
        make_msg(inbox_dir / "email1.msg", message_id="<diff-001@outlook.local>", sender_email="alice@example.com")
        make_msg(inbox_dir / "email2.msg", message_id="<diff-002@outlook.local>", sender_email="alice@example.com")

        parse_and_store_email(inbox_dir / "email1.msg", session)
        parse_and_store_email(inbox_dir / "email2.msg", session)

        assert session.query(Email).count() == 2

    def test_duplicate_file_is_deleted(self, session, inbox_dir):
        """The duplicate .msg file is removed from disk after merging."""
        msg_id = "<dup-del@outlook.local>"

        make_msg(inbox_dir / "email1.msg", message_id=msg_id, sender_email="alice@example.com")
        parse_and_store_email(inbox_dir / "email1.msg", session)

        path2 = inbox_dir / "email2.msg"
        make_msg(path2, message_id=msg_id, sender_email="bob@example.com")
        parse_and_store_email(path2, session)

        assert not path2.exists(), "Duplicate .msg file should be deleted"

    def test_duplicate_creates_processing_log(self, session, inbox_dir):
        """Merging a duplicate creates a processing log entry."""
        msg_id = "<dup-log@outlook.local>"

        make_msg(inbox_dir / "email1.msg", message_id=msg_id, sender_email="alice@example.com")
        parse_and_store_email(inbox_dir / "email1.msg", session)

        make_msg(inbox_dir / "email2.msg", message_id=msg_id, sender_email="bob@example.com")
        parse_and_store_email(inbox_dir / "email2.msg", session)

        logs = session.query(ProcessingLog).filter_by(status="success").all()
        merge_log = [l for l in logs if "Duplicate merged" in (l.message or "")]
        assert len(merge_log) == 1
        assert "bob@example.com" in merge_log[0].message

    def test_five_senders_same_msg(self, session, inbox_dir):
        """Five people forward the same .msg → 1 record, 4 merged senders."""
        msg_id = "<dup-five@outlook.local>"
        senders = [
            ("a@co.com", "A"), ("b@co.com", "B"), ("c@co.com", "C"),
            ("d@co.com", "D"), ("e@co.com", "E"),
        ]
        for i, (addr, name) in enumerate(senders):
            make_msg(inbox_dir / f"sender_{i}.msg", message_id=msg_id, sender_email=addr, sender_name=name)
            parse_and_store_email(inbox_dir / f"sender_{i}.msg", session)

        assert session.query(Email).count() == 1
        stored = session.query(Email).filter_by(message_id=msg_id).first()
        also = json.loads(stored.also_received_from)
        assert len(also) == 4

    def test_longer_body_promotes_to_primary(self, session, inbox_dir):
        """When a duplicate has a longer body, it replaces the primary."""
        msg_id = "<dup-promote@outlook.local>"
        short_body = "FYI — forwarding."
        long_body = (
            "All teams: production freeze begins Friday 5pm EST.\n\n"
            "No deploys, no database changes, no infrastructure modifications.\n\n"
            "Emergency hotfixes require VP approval.\n\n— Release Manager"
        )

        # Short forwarding note arrives first
        make_msg(inbox_dir / "fwd.msg", message_id=msg_id,
                 subject="FW: Production freeze",
                 body=short_body,
                 sender_email="forwarder@example.com", sender_name="Forwarder")
        parse_and_store_email(inbox_dir / "fwd.msg", session)

        # Original (longer) email arrives second
        make_msg(inbox_dir / "orig.msg", message_id=msg_id,
                 subject="Production freeze starts Friday",
                 body=long_body,
                 sender_email="manager@example.com", sender_name="Manager")
        parse_and_store_email(inbox_dir / "orig.msg", session)

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        # Manager should now be the primary sender
        assert stored.from_address == "manager@example.com"
        assert stored.from_name == "Manager"
        assert stored.subject == "Production freeze starts Friday"
        assert "production freeze begins" in stored.body_text
        # Forwarder should be in also_received_from
        also = json.loads(stored.also_received_from)
        assert len(also) == 1
        assert also[0]["address"] == "forwarder@example.com"

    def test_shorter_body_does_not_promote(self, session, inbox_dir):
        """When a duplicate has a shorter body, the original stays primary."""
        msg_id = "<dup-nopromote@outlook.local>"
        long_body = "Detailed original email with lots of important content and action items."
        short_body = "FYI."

        # Long original arrives first
        make_msg(inbox_dir / "orig.msg", message_id=msg_id,
                 body=long_body,
                 sender_email="original@example.com", sender_name="Original")
        parse_and_store_email(inbox_dir / "orig.msg", session)

        # Short forward arrives second
        make_msg(inbox_dir / "fwd.msg", message_id=msg_id,
                 body=short_body,
                 sender_email="forwarder@example.com", sender_name="Forwarder")
        parse_and_store_email(inbox_dir / "fwd.msg", session)

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        # Original should still be primary
        assert stored.from_address == "original@example.com"
        assert "Detailed original" in stored.body_text
        also = json.loads(stored.also_received_from)
        assert also[0]["address"] == "forwarder@example.com"

    def test_promotion_with_multiple_senders(self, session, inbox_dir):
        """Third sender with longest body promotes, prior two demoted."""
        msg_id = "<dup-multi-promote@outlook.local>"

        # Short forward #1
        make_msg(inbox_dir / "fwd1.msg", message_id=msg_id,
                 body="Forwarding.",
                 sender_email="fwd1@example.com", sender_name="Fwd1")
        parse_and_store_email(inbox_dir / "fwd1.msg", session)

        # Short forward #2
        make_msg(inbox_dir / "fwd2.msg", message_id=msg_id,
                 body="FYI.",
                 sender_email="fwd2@example.com", sender_name="Fwd2")
        parse_and_store_email(inbox_dir / "fwd2.msg", session)

        # Original with long body arrives third
        make_msg(inbox_dir / "orig.msg", message_id=msg_id,
                 body="This is the real email with detailed action items that everyone forwarded.",
                 sender_email="author@example.com", sender_name="Author")
        parse_and_store_email(inbox_dir / "orig.msg", session)

        stored = session.query(Email).filter_by(message_id=msg_id).first()
        assert stored.from_address == "author@example.com"
        also = json.loads(stored.also_received_from)
        addrs = {s["address"] for s in also}
        assert addrs == {"fwd1@example.com", "fwd2@example.com"}


# ---------------------------------------------------------------------------
# 2. CHAIN STRIPPING INTEGRATION TESTS
# ---------------------------------------------------------------------------

class TestChainStrippingIntegration:
    """Verify chain stripping works end-to-end with .msg files."""

    def _store_msg(self, session, inbox_dir, body, *, msg_id=None, subject="Test"):
        """Helper: create a .msg file, parse it, return the stored Email."""
        if msg_id is None:
            msg_id = f"<chain-{id(body)}@outlook.local>"
        filename = msg_id.replace("<", "").replace(">", "").replace("@", "_") + ".msg"
        make_msg(inbox_dir / filename, message_id=msg_id, subject=subject, body=body, sender_email="sender@example.com")
        return parse_and_store_email(inbox_dir / filename, session)

    def test_plain_email_body_unchanged(self, session, inbox_dir):
        """Email without quoting passes through to AI with body intact."""
        body = "Please submit the TPS report by Friday.\n\nThanks,\nBill"
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "TPS report" in stripped
        assert "Bill" in stripped

    def test_angle_bracket_quoting_stripped(self, session, inbox_dir):
        """Lines starting with > are removed before AI processing."""
        body = "I agree with the approach.\n\n> Can we use the new framework?\n> It would be much better for performance.\n"
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "I agree with the approach" in stripped
        assert "new framework" not in stripped

    def test_on_wrote_block_stripped(self, session, inbox_dir):
        """'On [date], [person] wrote:' and everything after is removed."""
        body = (
            "Sure, I can handle the deployment.\n\n"
            "On Mon, Feb 17, 2026 at 9:00 AM Sarah Connor <sarah@sky.net> wrote:\n"
            "Can someone handle the deployment this week?\n"
        )
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "I can handle the deployment" in stripped
        assert "Sarah Connor" not in stripped

    def test_original_message_block_stripped(self, session, inbox_dir):
        """'-----Original Message-----' and everything after is removed."""
        body = (
            "Got it, will review today.\n\n"
            "-----Original Message-----\n"
            "From: John Smith\nSent: Monday, February 17, 2026\nTo: Team\nSubject: Review\n\n"
            "The document is ready.\n"
        )
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "will review today" in stripped
        assert "John Smith" not in stripped

    def test_outlook_forwarded_headers_stripped(self, session, inbox_dir):
        """Outlook-style forwarded header blocks are removed."""
        body = (
            "FYI for awareness.\n\n"
            "From: Jane Doe <jane@example.com>\n"
            "Sent: Tuesday, February 18, 2026 3:00 PM\n"
            "To: All Staff <staff@example.com>\n"
            "Subject: Office closure\n\n"
            "The office will be closed on Friday.\n"
        )
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "FYI for awareness" in stripped
        assert "Office closure" not in stripped

    def test_deep_three_level_chain(self, session, inbox_dir):
        """A 3-level email chain only keeps the top-level reply."""
        body = (
            "Final approval granted.\n\n"
            "On Feb 17, 2026 at 2:00 PM Sarah wrote:\n"
            "I've reviewed the proposal.\n\n"
            "On Feb 16, 2026 at 9:00 AM Mike wrote:\n"
            "Here's the proposal.\n"
        )
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert "Final approval granted" in stripped
        assert "Sarah wrote" not in stripped
        assert "Mike wrote" not in stripped

    def test_entirely_quoted_returns_original(self, session, inbox_dir):
        """If the entire email is quoted, return original rather than empty."""
        body = "> This is all quoted content.\n> No original reply."
        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert stripped == body.strip()

    def test_chain_stripping_in_ai_client_extract(self, session, inbox_dir):
        """Verify chain stripping is called during AI action extraction."""
        body = (
            "Please send the report.\n\n"
            "On Feb 15, 2026 at 10:00 AM Old Sender wrote:\n"
            "This is old quoted content that should be stripped.\n"
        )
        email = self._store_msg(session, inbox_dir, body, subject="Report request")

        captured_prompts = []
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"actions": []})

        with patch("emailtools.ai.client.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            def capture_call(**kwargs):
                for msg in kwargs.get("messages", []):
                    if msg["role"] == "user":
                        captured_prompts.append(msg["content"])
                return mock_response

            mock_client.chat.completions.create.side_effect = capture_call

            from emailtools.ai.client import AIClient
            client = AIClient.__new__(AIClient)
            client.client = mock_client
            client.model = "gpt-4"
            client.max_retries = 1
            client.timeout = 30
            # Patch get_knowledge_context to avoid needing the KB table
            # in this test's isolated DB
            with patch("emailtools.ai.client.get_knowledge_context", return_value=""):
                client.extract_actions(email)

        assert len(captured_prompts) == 1
        assert "Please send the report" in captured_prompts[0]
        assert "old quoted content" not in captured_prompts[0]

    def test_long_chain_truncated_before_4000_char_limit(self, session, inbox_dir):
        """Chain stripping reduces body size before the 4000-char truncation."""
        reply = "Approved. Please proceed.\n\n"
        chain = "On Feb 1, 2026 at 10:00 AM LongWriter wrote:\n" + "x" * 6000
        body = reply + chain
        assert len(body) > 4000

        email = self._store_msg(session, inbox_dir, body)
        stripped = strip_quoted_text(email.body_text)
        assert len(stripped) < 100
        assert "Approved" in stripped


# ---------------------------------------------------------------------------
# 3. BATCH PROCESSING TESTS
# ---------------------------------------------------------------------------

class TestBatchProcessing:
    """Verify batch processing with rate limiting works correctly."""

    def _populate_emails(self, session, count):
        """Insert N unprocessed emails into the database."""
        emails = []
        for i in range(count):
            email = Email(
                message_id=f"<batch-{i:04d}@test.com>",
                subject=f"Batch email #{i+1}",
                from_address=f"sender{i}@example.com",
                to_addresses=json.dumps(["inbox@company.com"]),
                received_date=datetime.utcnow() - timedelta(hours=count - i),
                body_text=f"Action needed: complete task #{i+1} by next week.",
                processed=False,
            )
            session.add(email)
            emails.append(email)
        session.commit()
        return emails

    @patch("emailtools.ai.processor.get_ai_client")
    def test_all_emails_processed(self, mock_get_client, session):
        """All unprocessed emails are processed when no limit is set."""
        self._populate_emails(session, 15)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        processed, actions = process_unprocessed_emails(session, batch_size=5, batch_delay=0)
        assert processed == 15
        assert actions == 0

    @patch("emailtools.ai.processor.get_ai_client")
    def test_limit_respected(self, mock_get_client, session):
        """Only 'limit' emails are processed when limit is set."""
        self._populate_emails(session, 20)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        processed, actions = process_unprocessed_emails(session, limit=7, batch_size=5, batch_delay=0)
        assert processed == 7

    @patch("emailtools.ai.processor.get_ai_client")
    def test_already_processed_skipped(self, mock_get_client, session):
        """Emails marked as processed=True are not re-processed."""
        emails = self._populate_emails(session, 10)
        for e in emails[:5]:
            e.processed = True
            e.processed_at = datetime.utcnow()
        session.commit()

        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        processed, actions = process_unprocessed_emails(session, batch_size=5, batch_delay=0)
        assert processed == 5

    @patch("emailtools.ai.processor.get_ai_client")
    @patch("emailtools.ai.processor.time.sleep")
    def test_batch_delay_called_between_batches(self, mock_sleep, mock_get_client, session):
        """time.sleep is called between batches with the correct delay."""
        self._populate_emails(session, 12)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        process_unprocessed_emails(session, batch_size=5, batch_delay=3.0)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(3.0)

    @patch("emailtools.ai.processor.get_ai_client")
    @patch("emailtools.ai.processor.time.sleep")
    def test_no_delay_on_last_batch(self, mock_sleep, mock_get_client, session):
        """No delay after the final batch (no unnecessary wait)."""
        self._populate_emails(session, 10)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        process_unprocessed_emails(session, batch_size=5, batch_delay=2.0)
        assert mock_sleep.call_count == 1

    @patch("emailtools.ai.processor.get_ai_client")
    def test_actions_counted_correctly(self, mock_get_client, session):
        """Total actions count reflects all actions created across batches."""
        self._populate_emails(session, 6)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = (
            [{"title": "Action A", "priority": "high"}, {"title": "Action B", "priority": "low"}],
            '{"actions": [...]}'
        )

        def make_actions(email, action_dicts, raw):
            return [Action(email_id=email.id, title=ad["title"], priority=ad.get("priority", "medium")) for ad in action_dicts]

        mock_client.create_action_objects.side_effect = make_actions
        mock_get_client.return_value = mock_client

        processed, total_actions = process_unprocessed_emails(session, batch_size=3, batch_delay=0)
        assert processed == 6
        assert total_actions == 12

    @patch("emailtools.ai.processor.get_ai_client")
    def test_empty_inbox_returns_zero(self, mock_get_client, session):
        """No unprocessed emails → (0, 0) returned immediately."""
        processed, actions = process_unprocessed_emails(session, batch_size=5, batch_delay=0)
        assert processed == 0
        assert actions == 0
        mock_get_client.assert_not_called()

    @patch("emailtools.ai.processor.get_ai_client")
    @patch("emailtools.ai.processor.time.sleep")
    def test_single_email_no_delay(self, mock_sleep, mock_get_client, session):
        """A single email doesn't trigger any batch delay."""
        self._populate_emails(session, 1)
        mock_client = MagicMock()
        mock_client.extract_actions.return_value = ([], '{"actions": []}')
        mock_client.create_action_objects.return_value = []
        mock_get_client.return_value = mock_client

        process_unprocessed_emails(session, batch_size=5, batch_delay=2.0)
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# 4. VOLUME / END-TO-END TESTS
# ---------------------------------------------------------------------------

class TestVolumeProcessing:
    """Test processing many .msg files at once — simulating real-world volume."""

    def test_30_unique_msg_files_all_stored(self, session, inbox_dir):
        """30 unique .msg files with different message-ids are all stored."""
        for i in range(30):
            make_msg(
                inbox_dir / f"vol_{i:03d}.msg",
                message_id=f"<vol-{i:03d}@outlook.local>",
                subject=f"Volume test email #{i+1}",
                sender_email=f"sender{i}@example.com",
                sender_name=f"Sender {i}",
                body=f"Action needed: complete item #{i+1} by end of week.",
            )

        count = process_inbox(session, inbox_dir=inbox_dir)
        assert count == 30
        assert session.query(Email).count() == 30

    def test_30_msg_files_with_10_duplicates(self, session, inbox_dir):
        """30 .msg files where 10 share message-ids → 20 unique records."""
        # First 20 are unique (prefix 'a_' so they sort first in glob)
        for i in range(20):
            make_msg(
                inbox_dir / f"a_unique_{i:03d}.msg",
                message_id=f"<mix-{i:03d}@outlook.local>",
                subject=f"Unique email #{i+1}",
                sender_email=f"sender{i}@example.com",
            )

        # Next 10 duplicate the first 10 (different sender, prefix 'b_')
        for i in range(10):
            make_msg(
                inbox_dir / f"b_dup_{i:03d}.msg",
                message_id=f"<mix-{i:03d}@outlook.local>",
                subject=f"Unique email #{i+1}",
                sender_email=f"forwarder{i}@example.com",
                sender_name=f"Forwarder {i}",
            )

        count = process_inbox(session, inbox_dir=inbox_dir)
        assert count == 20

        assert session.query(Email).count() == 20

        for i in range(10):
            email = session.query(Email).filter_by(message_id=f"<mix-{i:03d}@outlook.local>").first()
            also = json.loads(email.also_received_from or "[]")
            assert len(also) == 1
            # File processing order varies by OS, so either sender could be primary
            all_senders = {email.from_address} | {a["address"] for a in also}
            assert all_senders == {f"sender{i}@example.com", f"forwarder{i}@example.com"}

    def test_50_msg_files_mixed_with_chains(self, session, inbox_dir):
        """50 .msg files: some plain, some with chains, some duplicates."""
        generated = 0

        # 20 plain emails
        for i in range(20):
            make_msg(
                inbox_dir / f"plain_{i:03d}.msg",
                message_id=f"<big-plain-{i:03d}@outlook.local>",
                subject=f"Plain email #{i+1}",
                sender_email=f"plain{i}@example.com",
                body=f"Simple action: review document #{i+1}.",
            )
            generated += 1

        # 15 emails with chains
        for i in range(15):
            chain_body = (
                f"My reply: approved item #{i+1}.\n\n"
                f"On Feb {10 + i % 28}, 2026 at 3:00 PM Previous Sender wrote:\n"
                f"Here is the original request about item #{i+1}.\nPlease review ASAP.\n"
            )
            make_msg(
                inbox_dir / f"chain_{i:03d}.msg",
                message_id=f"<big-chain-{i:03d}@outlook.local>",
                subject=f"RE: Chain email #{i+1}",
                sender_email=f"chain{i}@example.com",
                body=chain_body,
            )
            generated += 1

        # 10 emails with Outlook forwarded headers
        for i in range(10):
            fwd_body = (
                f"FYI — forwarding item #{i+1} for your awareness.\n\n"
                f"From: originator{i}@example.com\n"
                f"Sent: Monday, February {10+i}, 2026 9:00 AM\n"
                f"To: team@example.com\n"
                f"Subject: Item #{i+1} update\n\n"
                f"The original update about item #{i+1}.\n"
            )
            make_msg(
                inbox_dir / f"fwd_{i:03d}.msg",
                message_id=f"<big-fwd-{i:03d}@outlook.local>",
                subject=f"FW: Item #{i+1} update",
                sender_email=f"fwd{i}@example.com",
                body=fwd_body,
            )
            generated += 1

        # 5 duplicates of the first 5 plain emails (different sender)
        for i in range(5):
            make_msg(
                inbox_dir / f"dup_plain_{i:03d}.msg",
                message_id=f"<big-plain-{i:03d}@outlook.local>",
                subject=f"Plain email #{i+1}",
                sender_email=f"dup-plain{i}@example.com",
            )
            generated += 1

        assert generated == 50

        count = process_inbox(session, inbox_dir=inbox_dir)
        assert count == 45  # 50 - 5 duplicates
        assert session.query(Email).count() == 45

        # Verify chain stripping on a chain email
        chain_email = session.query(Email).filter_by(message_id="<big-chain-000@outlook.local>").first()
        stripped = strip_quoted_text(chain_email.body_text)
        assert "My reply: approved item #1" in stripped
        assert "Previous Sender wrote" not in stripped

        # Verify chain stripping on a forwarded email
        fwd_email = session.query(Email).filter_by(message_id="<big-fwd-000@outlook.local>").first()
        stripped = strip_quoted_text(fwd_email.body_text)
        assert "FYI" in stripped
        assert "The original update" not in stripped

    @patch("emailtools.ai.processor.get_ai_client")
    @patch("emailtools.ai.processor.time.sleep")
    def test_batch_processing_25_emails(self, mock_sleep, mock_get_client, session):
        """25 emails processed in batches of 10 with delays between batches."""
        for i in range(25):
            session.add(Email(
                message_id=f"<batch25-{i:03d}@test.com>",
                subject=f"Batch email #{i+1}",
                from_address=f"sender{i}@example.com",
                to_addresses=json.dumps(["inbox@company.com"]),
                received_date=datetime.utcnow() - timedelta(hours=25 - i),
                body_text=f"Please complete task #{i+1}.",
                processed=False,
            ))
        session.commit()

        mock_client = MagicMock()
        mock_client.extract_actions.return_value = (
            [{"title": "Do something", "priority": "medium", "confidence": 0.9}],
            '{"actions": [...]}'
        )
        mock_client.create_action_objects.side_effect = lambda email, ads, raw: [
            Action(email_id=email.id, title=ad["title"], priority=ad.get("priority", "medium"), confidence_score=ad.get("confidence"))
            for ad in ads
        ]
        mock_get_client.return_value = mock_client

        processed, total_actions = process_unprocessed_emails(session, batch_size=10, batch_delay=2.0)
        assert processed == 25
        assert total_actions == 25
        assert mock_sleep.call_count == 2
        assert session.query(Email).filter_by(processed=False).count() == 0

    def test_process_inbox_with_empty_directory(self, session, inbox_dir):
        """Empty inbox directory returns 0 processed."""
        assert process_inbox(session, inbox_dir=inbox_dir) == 0

    def test_process_inbox_ignores_non_email_files(self, session, inbox_dir):
        """Non-email files (.txt, .pdf) in inbox are ignored."""
        (inbox_dir / "notes.txt").write_text("Not an email")
        (inbox_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake")

        make_msg(inbox_dir / "real.msg", message_id="<only-msg@outlook.local>", sender_email="real@example.com")

        count = process_inbox(session, inbox_dir=inbox_dir)
        assert count == 1
        assert session.query(Email).count() == 1


# ---------------------------------------------------------------------------
# 5. CHAIN STRIPPING — REALISTIC EMAIL BODIES
# ---------------------------------------------------------------------------

class TestRealisticChainStripping:
    """Test chain stripping with realistic, complex email bodies."""

    def test_outlook_reply_all_chain(self):
        """Realistic Outlook Reply All chain with multiple levels."""
        body = (
            "Team,\n\nI've updated the deployment schedule.\n\nBest regards,\nSarah\n\n"
            "-----Original Message-----\n"
            "From: Mike Johnson <mike.johnson@company.com>\nSent: Monday, February 17, 2026 8:30 AM\n"
            "To: Engineering Team <eng@company.com>\nSubject: RE: Deployment Schedule Q1\n\n"
            "Sarah, can you update the timeline?\n\n"
            "-----Original Message-----\n"
            "From: Sarah Williams <sarah.w@company.com>\nSent: Friday, February 14, 2026 4:00 PM\n"
            "To: Engineering Team <eng@company.com>\nSubject: Deployment Schedule Q1\n\n"
            "Here is the Q1 deployment schedule.\n"
        )
        result = strip_quoted_text(body)
        assert "updated the deployment schedule" in result
        assert "Mike Johnson" not in result

    def test_gmail_style_chain(self):
        """Gmail-style chain with 'On X wrote:' markers."""
        body = (
            "Thanks for the update. I'll review the PR today.\n\n"
            "On Mon, Feb 17, 2026 at 11:23 AM David Chen <david.chen@startup.io> wrote:\n\n"
            "> I've pushed the fix to the feature branch. PR #342 is ready.\n"
            "> \n"
            "> On Mon, Feb 17, 2026 at 10:05 AM Lisa Park <lisa@startup.io> wrote:\n>\n"
            "> > Can someone look into the login bug?\n"
        )
        result = strip_quoted_text(body)
        assert "review the PR today" in result
        assert "David Chen" not in result
        assert "login bug" not in result

    def test_forwarded_message_marker(self):
        """Forwarded email with standard marker."""
        body = (
            "See the forwarded vendor quote below.\n\n"
            "---------- Forwarded message ----------\n"
            "From: Vendor Sales <sales@vendor.com>\nDate: Thu, Feb 13, 2026\n"
            "Subject: Quote for Project Alpha\nTo: Procurement\n\n"
            "Total: $125,000\n"
        )
        result = strip_quoted_text(body)
        assert "forwarded vendor quote" in result
        assert "$125,000" not in result

    def test_email_with_signature_before_chain(self):
        """Signature block preserved, chain stripped."""
        body = (
            "Sounds good. Let's schedule the meeting for Thursday.\n\n"
            "--\nJohn Smith | Senior PM\nPhone: (555) 123-4567\n\n"
            "On Feb 16, 2026 at 5:00 PM Amy wrote:\nCan we meet this week?\n"
        )
        result = strip_quoted_text(body)
        assert "schedule the meeting" in result
        assert "Senior PM" in result
        assert "Amy wrote" not in result

    def test_very_long_chain_10_levels(self):
        """10-level deep chain — only the latest reply is kept."""
        reply = "Final decision: we're going with Option B.\n\n"
        chain = ""
        for level in range(10):
            chain += f"On Feb {7 + level}, 2026 at {9 + level}:00 AM Person{level} wrote:\n"
            chain += f"Level {level} comment.\n\n"

        result = strip_quoted_text(reply + chain)
        assert "going with Option B" in result
        for level in range(10):
            assert f"Person{level} wrote" not in result

    def test_unicode_in_chain(self):
        """Email chain with unicode characters (accents, CJK)."""
        body = (
            "Merci beaucoup! Je suis d'accord.\n\n"
            "On Feb 17, 2026 at 2:00 PM François Müller <francois@example.de> wrote:\n"
            "Voici le rapport pour le projet 日本語テスト.\n"
        )
        result = strip_quoted_text(body)
        assert "Merci beaucoup" in result
        assert "François" not in result
        assert "日本語" not in result

    def test_email_with_only_whitespace_after_stripping(self):
        """Reply is only whitespace → fallback to original."""
        body = "   \n\nOn Feb 17, 2026 at 10:00 AM Someone wrote:\nImportant content here.\n"
        result = strip_quoted_text(body)
        assert "Important content" in result

    def test_email_no_body(self):
        """None and empty string edge cases."""
        assert strip_quoted_text(None) is None
        assert strip_quoted_text("") == ""

    def test_email_just_signature(self):
        """Signature-only email passes through."""
        body = "Thanks,\nBob"
        result = strip_quoted_text(body)
        assert "Thanks" in result
        assert "Bob" in result


# ---------------------------------------------------------------------------
# 6. REAL .MSG FILE PARSING TESTS
# ---------------------------------------------------------------------------

class TestMsgParsing:
    """Test .msg file handling using real generated OLE2 files (no mocks)."""

    def test_msg_fields_extracted_correctly(self, session, inbox_dir):
        """All fields are extracted from a real .msg file."""
        make_msg(
            inbox_dir / "full.msg",
            message_id="<msg-full@outlook.local>",
            subject="Quarterly Budget Review",
            body="Please review the attached budget proposal by Friday.",
            sender_name="John Doe",
            sender_email="john.doe@example.com",
        )
        result = parse_and_store_email(inbox_dir / "full.msg", session)

        assert result is not None
        assert result.message_id == "<msg-full@outlook.local>"
        assert result.subject == "Quarterly Budget Review"
        assert result.from_address == "john.doe@example.com"
        assert result.from_name == "John Doe"
        assert result.body_text == "Please review the attached budget proposal by Friday."

    def test_msg_with_chain_body(self, session, inbox_dir):
        """A real .msg file with a chain body gets stripped correctly."""
        chain_body = (
            "Approved — go ahead with the implementation.\n\n"
            "-----Original Message-----\n"
            "From: Developer <dev@company.com>\nSent: Monday, February 17, 2026 9:00 AM\n"
            "To: Manager <mgr@company.com>\nSubject: New Feature Proposal\n\n"
            "Can we implement the new dashboard feature?\n"
        )
        make_msg(inbox_dir / "chain.msg", message_id="<msg-chain@outlook.local>", body=chain_body, sender_email="mgr@company.com")
        result = parse_and_store_email(inbox_dir / "chain.msg", session)

        stripped = strip_quoted_text(result.body_text)
        assert "Approved" in stripped
        assert "go ahead with the implementation" in stripped
        assert "Developer" not in stripped
        assert "dashboard feature" not in stripped

    def test_msg_no_message_id_generates_fallback(self, session, inbox_dir):
        """A .msg file without a Message-ID gets a generated fallback."""
        make_msg(
            inbox_dir / "no_id.msg",
            message_id="",  # Empty ID → extract_msg returns empty string
            sender_email="someone@example.com",
        )
        result = parse_and_store_email(inbox_dir / "no_id.msg", session)

        assert result is not None
        assert result.message_id == "<no_id@outlook.local>"

    def test_msg_date_parsed(self, session, inbox_dir):
        """Date from .msg file is parsed correctly."""
        dt = datetime(2026, 3, 15, 9, 30, 0, tzinfo=timezone.utc)
        make_msg(inbox_dir / "dated.msg", message_id="<dated@outlook.local>", date=dt, sender_email="test@example.com")
        result = parse_and_store_email(inbox_dir / "dated.msg", session)

        assert result is not None
        assert result.received_date is not None
        # Date should be March 15, 2026 (timezone may shift)
        assert result.received_date.month == 3
        assert result.received_date.day == 15

    def test_msg_with_html_body(self, session, inbox_dir):
        """A .msg file with HTML body stores it correctly."""
        html = b"<html><body><p>Please <b>review</b> this.</p></body></html>"
        make_msg(
            inbox_dir / "html.msg",
            message_id="<html-msg@outlook.local>",
            body="Please review this.",
            html_body=html,
            sender_email="test@example.com",
        )
        result = parse_and_store_email(inbox_dir / "html.msg", session)

        assert result is not None
        assert result.body_text == "Please review this."
        # extract_msg may modify HTML slightly, just check it's present
        assert result.body_html is not None

    def test_msg_duplicate_merges_real_files(self, session, inbox_dir):
        """Duplicate real .msg files from different senders are merged."""
        msg_id = "<msg-dup-real@outlook.local>"

        make_msg(inbox_dir / "first.msg", message_id=msg_id, sender_email="alice@company.com", sender_name="Alice")
        parse_and_store_email(inbox_dir / "first.msg", session)

        make_msg(inbox_dir / "second.msg", message_id=msg_id, sender_email="bob@company.com", sender_name="Bob")
        parse_and_store_email(inbox_dir / "second.msg", session)

        assert session.query(Email).count() == 1
        stored = session.query(Email).filter_by(message_id=msg_id).first()
        also = json.loads(stored.also_received_from)
        assert len(also) == 1
        assert also[0]["address"] == "bob@company.com"
