"""Mock AI client for testing without OpenAI API calls."""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from emailtools.models import Action, Email
from emailtools.utils.logging import logger
from emailtools.priority_rules import PriorityRuleEngine
from emailtools.settings_service import SettingsService


class MockAIClient:
    """Mock AI client that simulates GPT-4 responses without API calls."""

    def __init__(self):
        """Initialize mock client."""
        logger.info("Using MOCK AI client (no API calls will be made)")

    def extract_actions(
        self,
        email: Email,
        current_date: datetime = None
    ) -> Tuple[List[Dict], str]:
        """
        Simulate GPT-4 action extraction with rule-based logic.

        Args:
            email: Email object to analyze
            current_date: Current date for deadline extraction

        Returns:
            Tuple of (list of action dicts, simulated raw response)
        """
        if current_date is None:
            current_date = datetime.utcnow()

        body = email.body_text or email.body_html or ""
        subject = email.subject.lower()

        actions = []

        # Rule 1: RFI detection
        if "rfi" in subject or "request for information" in body.lower():
            actions.append(self._create_rfi_action(email, body, current_date))

        # Rule 2: Multiple action items detection
        if "action item" in body.lower() or "following up" in body.lower():
            actions.extend(self._extract_numbered_actions(email, body, current_date))

        # Rule 3: Deliverable detection
        deliverable_keywords = ["provide", "submit", "send", "deliver", "complete"]
        for keyword in deliverable_keywords:
            if keyword in body.lower() and not any(a.get("title", "").lower().startswith(keyword) for a in actions):
                # Avoid duplicates, only add if not already captured
                pass

        # Rule 4: Questions requiring responses
        if "?" in body and "need" in body.lower():
            # Check if we haven't already captured this as an action
            if not actions:
                actions.append(self._create_question_action(email, body, current_date))

        # Rule 5: FYI emails (no actions)
        if "fyi" in subject.lower() or "for your information" in subject.lower():
            if "no action" in body.lower() or "no response needed" in body.lower():
                actions = []  # Clear any detected actions

        # If no actions detected, mark as informational
        if not actions:
            logger.info(f"Mock AI: No actions detected in email ID {email.id}")

        # Create simulated JSON response
        response_obj = {"actions": actions}
        raw_response = json.dumps(response_obj, indent=2)

        logger.info(f"Mock AI: Extracted {len(actions)} action(s) from email ID {email.id}")
        return actions, raw_response

    def _create_rfi_action(self, email: Email, body: str, current_date: datetime) -> Dict:
        """Create action for RFI emails."""
        # Extract deadline if mentioned
        due_date = self._extract_due_date(body, current_date)

        # Determine priority based on deadline
        if due_date and (due_date - current_date).days <= 3:
            priority = "high"
        elif due_date and (due_date - current_date).days <= 7:
            priority = "medium"
        else:
            priority = "low"

        # Extract what's being requested
        request_match = re.search(r"need\s+(.{10,100})", body, re.IGNORECASE)
        if request_match:
            request_desc = request_match.group(1).split('.')[0].strip()
        else:
            request_desc = email.subject

        return {
            "title": f"Respond to RFI: {request_desc[:50]}",
            "description": f"RFI received from {email.from_address}. Review email and provide requested information.",
            "priority": priority,
            "due_date": due_date.strftime("%Y-%m-%d") if due_date else None,
            "category": "RFI",
            "confidence": 0.95
        }

    def _extract_numbered_actions(self, email: Email, body: str, current_date: datetime) -> List[Dict]:
        """Extract numbered action items from email body."""
        actions = []

        # Look for numbered lists (1., 2., 3. or 1), 2), 3))
        pattern = r'(?:^|\n)\s*\d+[\.)]\s*\*?\*?(.+?)(?:\n|$)'
        matches = re.findall(pattern, body, re.MULTILINE)

        for i, match in enumerate(matches[:5]):  # Limit to first 5 items
            action_text = match.strip()

            # Skip if it's just a continuation of previous text
            if len(action_text) < 10:
                continue

            # Extract action title (first sentence)
            title = action_text.split('.')[0].strip()
            if len(title) > 100:
                title = title[:97] + "..."

            # Determine priority from keywords
            priority = "medium"  # default
            if any(word in action_text.lower() for word in ["urgent", "asap", "critical", "high priority"]):
                priority = "high"
            elif any(word in action_text.lower() for word in ["when possible", "low priority", "nice to have"]):
                priority = "low"

            # Extract due date if mentioned
            due_date = self._extract_due_date(action_text, current_date)

            # Determine category
            category = "deliverable"
            if "audit" in action_text.lower() or "security" in action_text.lower():
                category = "deliverable"
            elif "document" in action_text.lower() or "update" in action_text.lower():
                category = "deliverable"
            elif "analysis" in action_text.lower() or "review" in action_text.lower():
                category = "deliverable"

            actions.append({
                "title": title,
                "description": action_text[:200],
                "priority": priority,
                "due_date": due_date.strftime("%Y-%m-%d") if due_date else None,
                "category": category,
                "confidence": 0.85
            })

        return actions

    def _create_question_action(self, email: Email, body: str, current_date: datetime) -> Dict:
        """Create action for emails with questions."""
        # Find the question
        questions = [s.strip() for s in body.split('?') if s.strip()]
        if questions:
            question = questions[0][:100]
        else:
            question = email.subject

        return {
            "title": f"Respond to question: {question}",
            "description": f"Email from {email.from_address} requires response.",
            "priority": "medium",
            "due_date": None,
            "category": "stakeholder_request",
            "confidence": 0.75
        }

    def _extract_due_date(self, text: str, current_date: datetime) -> datetime:
        """Extract due date from text using simple pattern matching."""
        text_lower = text.lower()

        # Pattern: "by Friday", "by Feb 20", "by end of week"
        day_patterns = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }

        # Check for day of week
        for day_name, day_num in day_patterns.items():
            if f"by {day_name}" in text_lower or f"before {day_name}" in text_lower:
                days_ahead = (day_num - current_date.weekday() + 7) % 7
                if days_ahead == 0:  # If today, assume next week
                    days_ahead = 7
                return current_date + timedelta(days=days_ahead)

        # Check for specific dates (e.g., "Feb 20", "February 20")
        date_match = re.search(r'(?:by|before)\s+(?:feb(?:ruary)?|jan(?:uary)?|mar(?:ch)?)\s+(\d{1,2})', text_lower)
        if date_match:
            day = int(date_match.group(1))
            # Assume current year, current or next month
            return datetime(current_date.year, current_date.month, day)

        # Check for "end of week"
        if "end of week" in text_lower or "eow" in text_lower:
            days_until_friday = (4 - current_date.weekday() + 7) % 7
            return current_date + timedelta(days=days_until_friday)

        # Check for relative days
        if "tomorrow" in text_lower:
            return current_date + timedelta(days=1)
        elif "in 3 days" in text_lower or "within 3 days" in text_lower:
            return current_date + timedelta(days=3)

        return None

    def create_action_objects(
        self,
        email: Email,
        action_dicts: List[Dict],
        raw_ai_response: str
    ) -> List[Action]:
        """
        Convert action dictionaries to Action ORM objects.
        (Same implementation as real AI client)
        """
        confidence_threshold = SettingsService.get_ai_config()['confidence_threshold']
        actions = []

        for action_dict in action_dicts:
            try:
                # Skip actions below confidence threshold
                confidence = action_dict.get("confidence")
                if confidence is not None and confidence < confidence_threshold:
                    logger.info(f"Skipping low-confidence action (score={confidence:.2f} < threshold={confidence_threshold}): '{action_dict.get('title', '')[:60]}'")
                    continue

                # Parse due_date if present
                due_date = None
                if action_dict.get("due_date"):
                    try:
                        due_date = datetime.strptime(action_dict["due_date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse due_date: {action_dict.get('due_date')}")

                # Get AI-suggested priority
                ai_priority = action_dict.get("priority")

                # Apply priority rules to get final priority
                final_priority = PriorityRuleEngine.apply_priority_rules(
                    email_from=email.from_address,
                    email_subject=email.subject,
                    email_body=email.body_text or email.body_html or "",
                    due_date=due_date,
                    ai_priority=ai_priority
                )

                action = Action(
                    email_id=email.id,
                    title=action_dict.get("title", "Untitled Action")[:500],
                    description=action_dict.get("description"),
                    priority=final_priority,  # Use rule-adjusted priority
                    due_date=due_date,
                    category=action_dict.get("category"),
                    confidence_score=action_dict.get("confidence"),
                    raw_ai_response=raw_ai_response
                )

                actions.append(action)

                # Log if priority was overridden
                if ai_priority and ai_priority != final_priority:
                    logger.info(f"Priority override: {ai_priority} → {final_priority} for '{action.title[:50]}'")
                else:
                    logger.debug(f"Mock AI: Created action: {action.title}")

            except Exception as e:
                logger.error(f"Failed to create Action object: {e}")
                continue

        return actions

    def generate_program_news(self, emails: List[Email], days: int = 7) -> str:
        """
        Generate a mock program news summary.

        Args:
            emails: List of recent emails
            days: Number of days covered

        Returns:
            Mock summary text
        """
        if not emails:
            return "No email activity in the past {} days.".format(days)

        # Count emails by domain
        domain_counts = {}
        for email in emails:
            domain = email.from_address.split('@')[-1]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Build summary
        summary_parts = []

        summary_parts.append(
            f"Over the past {days} days, the team received {len(emails)} emails from various stakeholders. "
        )

        # Top senders
        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_domains:
            domain_list = ", ".join([f"{domain} ({count})" for domain, count in top_domains])
            summary_parts.append(
                f"Most communication came from: {domain_list}. "
            )

        # Processed vs unprocessed
        processed_count = sum(1 for e in emails if e.processed)
        if processed_count == len(emails):
            summary_parts.append("All emails have been processed and analyzed for action items. ")
        else:
            summary_parts.append(
                f"{processed_count} of {len(emails)} emails have been processed. "
            )

        # General status
        summary_parts.append(
            "The team continues to address stakeholder requests and RFIs. "
            "Key focus areas include compliance deliverables, technical documentation updates, "
            "and ongoing infrastructure improvements."
        )

        return "".join(summary_parts)


# Singleton instance
mock_ai_client = MockAIClient()
