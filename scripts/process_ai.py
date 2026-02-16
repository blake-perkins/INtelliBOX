"""Process all unprocessed emails with AI."""

from emailtools.database import get_session
from emailtools.ai.processor import process_unprocessed_emails


def main():
    """Process all unprocessed emails."""
    with get_session() as session:
        emails_processed, total_actions = process_unprocessed_emails(session)
        print(f"\n[OK] Processed {emails_processed} email(s)")
        print(f"[OK] Extracted {total_actions} action(s)")


if __name__ == "__main__":
    main()
