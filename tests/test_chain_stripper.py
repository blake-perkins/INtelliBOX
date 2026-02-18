"""Tests for email chain stripping utility."""

from emailtools.ingestion.chain_stripper import strip_quoted_text


class TestStripQuotedText:
    """Test suite for strip_quoted_text function."""

    def test_no_quoted_text_passthrough(self):
        """Plain email body without quotes passes through unchanged."""
        body = "Hi team,\n\nPlease submit the report by Friday.\n\nThanks,\nJohn"
        assert strip_quoted_text(body) == body.strip()

    def test_empty_body(self):
        """Empty string returns empty string."""
        assert strip_quoted_text("") == ""

    def test_none_body(self):
        """None returns None."""
        assert strip_quoted_text(None) is None

    def test_strip_angle_bracket_quoting(self):
        """Lines starting with > are removed."""
        body = "I agree with this.\n\n> Original message here\n> More quoted text"
        result = strip_quoted_text(body)
        assert "I agree with this." in result
        assert "Original message here" not in result

    def test_strip_on_wrote_block(self):
        """'On [date], [person] wrote:' and everything after is removed."""
        body = (
            "Sure, I can do that.\n\n"
            "On Mon, Jan 1, 2026 at 10:00 AM John Doe <john@example.com> wrote:\n"
            "Hey, can you handle this?\n"
        )
        result = strip_quoted_text(body)
        assert "Sure, I can do that." in result
        assert "John Doe" not in result
        assert "can you handle this" not in result

    def test_strip_original_message(self):
        """'-----Original Message-----' and everything after is removed."""
        body = (
            "Got it, will handle.\n\n"
            "-----Original Message-----\n"
            "From: Jane Smith\n"
            "Sent: Monday, January 1, 2026\n"
            "Subject: Action needed\n\n"
            "Please review the attached.\n"
        )
        result = strip_quoted_text(body)
        assert "Got it, will handle." in result
        assert "Jane Smith" not in result
        assert "Action needed" not in result

    def test_strip_outlook_forwarded_headers(self):
        """Outlook-style forwarded header blocks are removed."""
        body = (
            "FYI, see below.\n\n"
            "From: Bob Jones <bob@example.com>\n"
            "Sent: Tuesday, February 1, 2026 3:00 PM\n"
            "To: Team <team@example.com>\n"
            "Subject: Budget update\n\n"
            "Here is the budget update.\n"
        )
        result = strip_quoted_text(body)
        assert "FYI, see below." in result
        assert "Budget update" not in result

    def test_strip_underscore_divider(self):
        """Underscore dividers (5+) and everything after is removed."""
        body = "My reply here.\n\n________________________________________\nForwarded content below."
        result = strip_quoted_text(body)
        assert "My reply here." in result
        assert "Forwarded content below" not in result

    def test_strip_forwarded_message_marker(self):
        """'---------- Forwarded message ----------' is recognized."""
        body = (
            "Forwarding this to you.\n\n"
            "---------- Forwarded message ----------\n"
            "From: Alice <alice@example.com>\n"
            "Date: Jan 1, 2026\n"
            "Subject: FYI\n\n"
            "Original content here.\n"
        )
        result = strip_quoted_text(body)
        assert "Forwarding this to you." in result
        assert "Original content here" not in result

    def test_entirely_quoted_returns_original(self):
        """If the entire body is quoted, return the original rather than empty."""
        body = "> This is all quoted\n> No original content"
        result = strip_quoted_text(body)
        assert result == body.strip()

    def test_deep_chain_only_keeps_latest(self):
        """A multi-level chain only keeps the top-level reply."""
        body = (
            "Thanks for the update.\n\n"
            "On Feb 15, 2026 at 2:00 PM Sarah wrote:\n"
            "Here's the status.\n\n"
            "On Feb 14, 2026 at 9:00 AM Mike wrote:\n"
            "Can you send a status update?\n"
        )
        result = strip_quoted_text(body)
        assert "Thanks for the update." in result
        assert "Sarah wrote" not in result
        assert "Mike wrote" not in result

    def test_mixed_quoting_styles(self):
        """Body with both > quoting and On wrote: block."""
        body = (
            "I'll take care of it.\n\n"
            "> Quick question about the deadline.\n\n"
            "On Jan 5, 2026 at 3:00 PM Bob wrote:\n"
            "> Original question here\n"
        )
        result = strip_quoted_text(body)
        assert "I'll take care of it." in result
        assert "Quick question" not in result
