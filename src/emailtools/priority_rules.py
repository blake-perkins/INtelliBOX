"""Priority rule engine for overriding AI-suggested priorities."""

from datetime import datetime, timedelta
from typing import Optional
from .settings_service import SettingsService


class PriorityRuleEngine:
    """Apply configurable priority rules to actions."""

    @staticmethod
    def apply_priority_rules(
        email_from: str,
        email_subject: str,
        email_body: str,
        due_date: Optional[datetime],
        ai_priority: str
    ) -> str:
        """
        Apply priority rules and return the final priority.

        Rules are checked in this order:
        1. High-priority sender match
        2. High-priority keyword match
        3. Due date within threshold
        4. Default priority

        Args:
            email_from: Sender email address
            email_subject: Email subject line
            email_body: Email body text
            due_date: Action due date (if extracted)
            ai_priority: AI-suggested priority

        Returns:
            Final priority: "high", "medium", or "low"
        """
        config = SettingsService.get_priority_config()

        # Rule 1: Check high-priority senders
        high_senders = config.get('high_senders', [])
        for sender_pattern in high_senders:
            if PriorityRuleEngine._matches_sender(email_from, sender_pattern):
                return "high"

        # Rule 2: Check high-priority keywords in subject/body
        high_keywords = config.get('high_keywords', [])
        search_text = f"{email_subject} {email_body}".lower()
        for keyword in high_keywords:
            if keyword.lower() in search_text:
                return "high"

        # Rule 3: Check due date threshold
        if due_date:
            days_threshold = config.get('days_threshold', 5)
            days_until_due = (due_date - datetime.utcnow()).days

            if days_until_due <= days_threshold:
                return "high"

        # Rule 4: Use default priority if AI priority is not set
        if not ai_priority or ai_priority not in ["high", "medium", "low"]:
            return config.get('default_priority', 'medium')

        # Otherwise, keep AI-suggested priority
        return ai_priority

    @staticmethod
    def _matches_sender(email_from: str, pattern: str) -> bool:
        """
        Check if email_from matches the sender pattern.

        Patterns can be:
        - Full email: "user@domain.com"
        - Domain only: "@domain.com"
        - Partial domain: "domain.com"

        Args:
            email_from: Email address to check
            pattern: Sender pattern to match

        Returns:
            True if matches, False otherwise
        """
        email_from_lower = email_from.lower()
        pattern_lower = pattern.lower()

        # Full email match
        if pattern_lower == email_from_lower:
            return True

        # Domain-only pattern (starts with @)
        if pattern_lower.startswith('@'):
            return email_from_lower.endswith(pattern_lower)

        # Partial domain match (e.g., "company.com" matches "user@company.com")
        if '@' not in pattern_lower:
            return pattern_lower in email_from_lower

        return False
