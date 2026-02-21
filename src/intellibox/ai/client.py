"""OpenAI GPT-4 client for email analysis."""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from intellibox.ai.prompts import (
    ACTION_EXTRACTION_PROMPT,
    PROGRAM_NEWS_PROMPT,
    STRUCTURED_PROGRAM_NEWS_PROMPT,
    SYSTEM_PROMPT,
)
from intellibox.config import settings
from intellibox.knowledge import get_knowledge_context
from intellibox.models import Action, Email
from intellibox.priority_rules import PriorityRuleEngine
from intellibox.settings_service import SettingsService
from intellibox.utils.datetime_utils import utcnow
from intellibox.utils.logging import logger

# Exceptions eligible for automatic retry
_RETRYABLE_EXCEPTIONS = (RateLimitError, APIConnectionError, APIError)


def strip_markdown_json(text: str) -> str:
    """
    Strip markdown code fences from JSON response.

    GPT-4 sometimes wraps JSON in ```json ... ``` blocks.
    This function removes those fences to get clean JSON.

    Args:
        text: Raw response text that may contain markdown

    Returns:
        Clean JSON string
    """
    text = text.strip()

    # Check if wrapped in markdown code fences
    if text.startswith("```"):
        # Remove opening fence (```json or just ```)
        lines = text.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]  # Remove first line

        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove last line

        text = '\n'.join(lines).strip()

    return text


class AIClient:
    """Client for interacting with OpenAI GPT-4 API."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_retries = settings.openai_max_retries
        self.timeout = settings.openai_timeout

    def _build_system_prompt(self) -> str:
        """Build system prompt with optional knowledge base context."""
        kb_context = get_knowledge_context()
        if not kb_context:
            return SYSTEM_PROMPT
        return (
            SYSTEM_PROMPT
            + "\n\n## Program Knowledge Base\n"
            "The following documents have been uploaded as program context. "
            "Use this information to better understand program terminology, "
            "deliverables, processes, and priorities.\n\n"
            + kb_context
        )

    def _call_api(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> str:
        """Call the OpenAI API with automatic retry and exponential backoff.

        Args:
            messages: Chat messages to send
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Raw response content string

        Raises:
            The original exception after max_retries exhausted
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout,
                )
                return response.choices[0].message.content
            except _RETRYABLE_EXCEPTIONS as e:
                if attempt < self.max_retries:
                    wait = 2 ** attempt  # 1, 2, 4, 8, ...
                    logger.warning(
                        f"API error (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {wait}s: {e}"
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"API error after {self.max_retries + 1} attempts, giving up: {e}"
                    )
                    raise

    def extract_actions(
        self,
        email: Email,
        current_date: Optional[datetime] = None,
        additional_context: Optional[str] = None,
    ) -> tuple[List[Dict], str]:
        """
        Extract action items from an email using GPT-4.

        Args:
            email: Email object to analyze
            current_date: Current date for deadline extraction (defaults to now)
            additional_context: Optional extra context to append to the email body

        Returns:
            Tuple of (list of action dicts, raw AI response)

        Raises:
            APIError: If OpenAI API fails
        """
        if current_date is None:
            current_date = utcnow()

        # Prepare email body (prefer plain text, fallback to HTML)
        from intellibox.ingestion.chain_stripper import strip_quoted_text
        body = email.body_text or email.body_html or "(No body content)"
        body = strip_quoted_text(body)
        if additional_context:
            body = body + "\n\n--- Additional Context Provided ---\n" + additional_context

        # Format the prompt with dynamic categories
        ai_config = SettingsService.get_ai_config()
        categories_text = SettingsService.format_categories_for_prompt(ai_config['categories'])
        prompt = ACTION_EXTRACTION_PROMPT.format(
            subject=email.subject,
            from_name=email.from_name or email.from_address,
            from_address=email.from_address,
            date=email.received_date.strftime("%Y-%m-%d %H:%M"),
            body=body[:4000],  # Limit body to 4000 chars to stay within token limits
            current_date=current_date.strftime("%Y-%m-%d"),
            categories=categories_text
        )

        logger.info(f"Calling GPT-4 API for email ID {email.id}")

        system_prompt = self._build_system_prompt()
        raw_response = self._call_api(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        logger.debug(f"GPT-4 response: {raw_response[:200]}...")

        # Parse JSON response (strip markdown code fences if present)
        try:
            clean_json = strip_markdown_json(raw_response)
            parsed = json.loads(clean_json)
            actions = parsed.get("actions", [])

            logger.info(f"Extracted {len(actions)} action(s) from email ID {email.id}")
            return actions, raw_response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT-4 JSON response: {e}")
            logger.error(f"Raw response: {raw_response}")
            return [], raw_response

    def create_action_objects(
        self,
        email: Email,
        action_dicts: List[Dict],
        raw_ai_response: str
    ) -> List[Action]:
        """
        Convert action dictionaries to Action ORM objects.

        Args:
            email: Parent email object
            action_dicts: List of action dicts from GPT-4
            raw_ai_response: Raw AI response for debugging

        Returns:
            List of Action ORM objects
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
                    title=action_dict.get("title", "Untitled Action")[:500],  # Limit length
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
                    logger.debug(f"Created action: {action.title}")

            except Exception as e:
                logger.error(f"Failed to create Action object: {e}")
                logger.error(f"Action dict: {action_dict}")
                continue

        return actions

    def generate_program_news(self, emails: List[Email], days: int = 7) -> str:
        """
        Generate a program news summary from recent emails.

        Args:
            emails: List of recent emails to summarize
            days: Number of days covered

        Returns:
            Generated summary text
        """
        if not emails:
            return "No recent email activity to summarize."

        # Create brief summaries of each email
        email_summaries = []
        for email in emails[:20]:  # Limit to 20 most recent
            summary = f"- From {email.from_address}: {email.subject}"
            email_summaries.append(summary)

        summaries_text = "\n".join(email_summaries)

        prompt = PROGRAM_NEWS_PROMPT.format(
            days=days,
            email_summaries=summaries_text
        )

        try:
            logger.info(f"Generating program news from {len(emails)} emails")

            system_prompt = self._build_system_prompt()
            summary = self._call_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500,
            ).strip()

            logger.info("Program news summary generated")
            return summary

        except Exception as e:
            logger.error(f"Failed to generate program news: {e}")
            return "Error generating program news summary."

    def generate_structured_program_news(self, emails: List[Email], days: int = 7) -> Dict:
        """
        Generate a structured program news summary with sections.

        Args:
            emails: List of recent emails to summarize
            days: Number of days covered

        Returns:
            Dictionary with structured news sections
        """
        if not emails:
            return {
                "critical_updates": [],
                "trending_topics": [],
                "volume_summary": {
                    "total_emails": 0,
                    "trend_description": "No activity",
                    "notable_pattern": ""
                },
                "top_senders": [],
                "key_takeaways": ["No recent email activity"]
            }

        # Create brief summaries of each email
        email_summaries = []
        for email in emails[:20]:  # Limit to 20 most recent
            summary = f"- From {email.from_address}: {email.subject}"
            email_summaries.append(summary)

        summaries_text = "\n".join(email_summaries)

        prompt = STRUCTURED_PROGRAM_NEWS_PROMPT.format(
            days=days,
            email_count=len(emails),
            email_summaries=summaries_text
        )

        try:
            logger.info(f"Generating structured program news from {len(emails)} emails")

            system_prompt = self._build_system_prompt()
            raw_response = self._call_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=800,
            ).strip()

            logger.debug(f"Structured program news response: {raw_response[:200]}...")

            try:
                clean_json = strip_markdown_json(raw_response)
                structured_news = json.loads(clean_json)
                logger.info("Structured program news generated successfully")
                return structured_news

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse structured news JSON: {e}")
                logger.error(f"Raw response: {raw_response}")
                return {
                    "critical_updates": [],
                    "trending_topics": [],
                    "volume_summary": {
                        "total_emails": len(emails),
                        "trend_description": "Unable to analyze",
                        "notable_pattern": ""
                    },
                    "top_senders": [],
                    "key_takeaways": ["Error parsing AI response - check logs"]
                }

        except Exception as e:
            logger.error(f"Failed to generate structured program news: {e}")
            return {
                "critical_updates": [],
                "trending_topics": [],
                "volume_summary": {
                    "total_emails": len(emails),
                    "trend_description": f"Error: {str(e)[:50]}",
                    "notable_pattern": ""
                },
                "top_senders": [],
                "key_takeaways": ["Error generating structured news"]
            }

    def generate_report_insights(
        self,
        action_details: str,
        email_summaries: str,
        days: int = 7,
        pipeline_stats: Dict = None
    ) -> Dict:
        """
        Generate KB-aware program intelligence briefing.

        Args:
            action_details: Pre-formatted text listing all actions with details
            email_summaries: Pre-formatted text listing recent email subjects
            days: Number of days covered
            pipeline_stats: Pipeline metrics dict with keys: total_actions,
                unassigned, high, medium, low, assigned_in_progress,
                completed, overdue, due_this_week

        Returns:
            Dictionary with structured insights (SOW alignment, risk radar,
            process compliance, trend intelligence)
        """
        _empty = {
            "executive_summary": {
                "headline": "No recent activity to report",
                "key_finding": "",
                "top_risk": "",
                "recommended_action": ""
            },
            "sow_alignment": {"mapped_deliverables": [], "unmapped_actions": [], "coverage_gaps": []},
            "risk_radar": [],
            "process_compliance": {"observations": [], "overall_health": "green"},
            "trend_intelligence": {"patterns": [], "workload_forecast": ""},
            "recommendations": []
        }

        if not action_details and not email_summaries:
            return _empty

        stats = pipeline_stats or {}

        prompt_template = SettingsService.get_insights_prompt()
        prompt = prompt_template.format(
            action_details=action_details or "No actions in pipeline",
            total_actions=stats.get("total_actions", 0),
            unassigned_count=stats.get("unassigned", 0),
            high_priority_count=stats.get("high", 0),
            medium_priority_count=stats.get("medium", 0),
            low_priority_count=stats.get("low", 0),
            assigned_in_progress=stats.get("assigned_in_progress", 0),
            completed_count=stats.get("completed", 0),
            overdue_count=stats.get("overdue", 0),
            due_this_week_count=stats.get("due_this_week", 0),
            days=days,
            email_summaries=email_summaries or "No recent emails"
        )

        try:
            logger.info(f"Generating KB-aware insights ({stats.get('total_actions', 0)} actions, {days}d)")

            system_prompt = self._build_system_prompt()
            raw_response = self._call_api(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=2000,
            ).strip()

            logger.debug(f"Report insights response: {raw_response[:200]}...")

            try:
                clean_json = strip_markdown_json(raw_response)
                insights = json.loads(clean_json)
                logger.info("Report insights generated successfully")
                return insights

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse insights JSON: {e}")
                logger.error(f"Raw response: {raw_response}")
                return {**_empty, "executive_summary": {**_empty["executive_summary"], "headline": "Unable to generate insights at this time"}}

        except Exception as e:
            logger.error(f"Failed to generate report insights: {e}")
            return {**_empty, "executive_summary": {**_empty["executive_summary"], "headline": f"Error: {str(e)[:80]}"}}


# Singleton instance
ai_client = AIClient()
