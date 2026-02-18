"""Reset and reprocess all emails with real GPT-4."""

from intellibox.database import get_session
from intellibox.models import Email, Action, Assignment
from intellibox.ai.processor import process_unprocessed_emails


def main():
    """Reset actions and reprocess emails with GPT-4."""
    with get_session() as session:
        # Count current state
        email_count = session.query(Email).count()
        action_count = session.query(Action).count()

        print(f"Current state:")
        print(f"  Emails: {email_count}")
        print(f"  Actions: {action_count} (from Demo Mode)")

        # Delete old actions and assignments
        print("\nClearing old Demo Mode actions...")
        session.query(Assignment).delete()
        session.query(Action).delete()

        # Mark all emails as unprocessed
        print("Marking all emails as unprocessed...")
        session.query(Email).update({
            Email.processed: False,
            Email.processed_at: None
        })

        session.commit()
        print("[OK] Database reset complete")

        # Now reprocess with GPT-4
        print("\n" + "="*60)
        print("PROCESSING WITH REAL GPT-4")
        print("="*60)
        print("This will make API calls and incur charges (~$0.30 for 10 emails)")
        print()

        emails_processed, total_actions = process_unprocessed_emails(session)

        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"Emails processed: {emails_processed}")
        print(f"Actions extracted: {total_actions}")
        print(f"\nDemo Mode found:  3 actions")
        print(f"GPT-4 found:      {total_actions} actions")
        print(f"Improvement:      +{total_actions - 3} actions")


if __name__ == "__main__":
    main()
