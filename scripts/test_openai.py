"""Test OpenAI API connection."""

from intellibox.ai.processor import get_ai_client
from intellibox.config import settings


def main():
    """Test OpenAI API connection."""
    print("Testing OpenAI API connection...")
    print(f"\nAPI Key configured: {settings.openai_api_key[:20]}..." if len(settings.openai_api_key) > 20 else settings.openai_api_key)

    # Get client
    client = get_ai_client()

    # Check which client we got
    if hasattr(client, '__class__'):
        client_type = client.__class__.__name__
        print(f"Client type: {client_type}")

        if "Mock" in client_type:
            print("\n[DEMO MODE] Using mock AI client (no API calls)")
            print("To use real GPT-4, update OPENAI_API_KEY in .env file")
        else:
            print("\n[REAL MODE] Using OpenAI GPT-4 API")
            print("API calls will be made and charged to your account")

            # Try a simple test
            try:
                print("\nTesting API with a simple email...")
                from intellibox.models import Email
                from datetime import datetime

                # Create a test email object (not saved to DB)
                test_email = Email(
                    id=999,
                    message_id="<test@example.com>",
                    subject="RFI: Need Q4 metrics by Friday",
                    from_address="boss@example.com",
                    from_name="Boss",
                    to_addresses='["you@example.com"]',
                    received_date=datetime.now(),
                    body_text="Hi team,\n\nCan you please send me the Q4 performance metrics by end of day Friday?\n\nThanks,\nBoss",
                    processed=False
                )

                actions, raw = client.extract_actions(test_email)
                print(f"\n[SUCCESS] API call worked!")
                print(f"Extracted {len(actions)} action(s) from test email:")
                for i, action in enumerate(actions, 1):
                    print(f"\n  {i}. {action.get('title', 'N/A')}")
                    print(f"     Priority: {action.get('priority', 'N/A')}")
                    print(f"     Category: {action.get('category', 'N/A')}")

            except Exception as e:
                print(f"\n[ERROR] API call failed: {e}")
                print("\nPossible issues:")
                print("  - Invalid API key")
                print("  - No billing method on OpenAI account")
                print("  - Network connectivity issue")
                return 1

    return 0


if __name__ == "__main__":
    exit(main())
