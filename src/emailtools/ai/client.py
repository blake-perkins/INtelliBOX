"""OpenAI GPT-4 client for email analysis."""

import json
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError

from emailtools.ai.prompts import ACTION_EXTRACTION_PROMPT, PROGRAM_NEWS_PROMPT, SYSTEM_PROMPT
from emailtools.config import settings
from emailtools.models import Action, Email
from emailtools.utils.logging import logger


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

    def extract_actions(
        self,
        email: Email,
        current_date: Optional[datetime] = None
    ) -> tuple[List[Dict], str]:
        """
        Extract action items from an email using GPT-4.

        Args:
            email: Email object to analyze
            current_date: Current date for deadline extraction (defaults to now)

        Returns:
            Tuple of (list of action dicts, raw AI response)

        Raises:
            APIError: If OpenAI API fails
        """
        if current_date is None:
            current_date = datetime.utcnow()

        # Prepare email body (prefer plain text, fallback to HTML)
        body = email.body_text or email.body_html or "(No body content)"

        # Format the prompt
        prompt = ACTION_EXTRACTION_PROMPT.format(
            subject=email.subject,
            from_name=email.from_name or email.from_address,
            from_address=email.from_address,
            date=email.received_date.strftime("%Y-%m-%d %H:%M"),
            body=body[:4000],  # Limit body to 4000 chars to stay within token limits
            current_date=current_date.strftime("%Y-%m-%d")
        )

        try:
            logger.info(f"Calling GPT-4 API for email ID {email.id}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent extraction
                max_tokens=1500,
                timeout=self.timeout
            )

            raw_response = response.choices[0].message.content
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

        except RateLimitError:
            logger.error("OpenAI API rate limit exceeded")
            raise
        except APIConnectionError as e:
            logger.error(f"Failed to connect to OpenAI API: {e}")
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI API: {e}")
            raise

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
        actions = []

        for action_dict in action_dicts:
            try:
                # Parse due_date if present
                due_date = None
                if action_dict.get("due_date"):
                    try:
                        due_date = datetime.strptime(action_dict["due_date"], "%Y-%m-%d")
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse due_date: {action_dict.get('due_date')}")

                action = Action(
                    email_id=email.id,
                    title=action_dict.get("title", "Untitled Action")[:500],  # Limit length
                    description=action_dict.get("description"),
                    priority=action_dict.get("priority"),
                    due_date=due_date,
                    category=action_dict.get("category"),
                    confidence_score=action_dict.get("confidence"),
                    raw_ai_response=raw_ai_response
                )

                actions.append(action)
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

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,  # Slightly higher for more natural prose
                max_tokens=500,
                timeout=self.timeout
            )

            summary = response.choices[0].message.content.strip()
            logger.info("Program news summary generated")

            return summary

        except Exception as e:
            logger.error(f"Failed to generate program news: {e}")
            return "Error generating program news summary."


# Singleton instance
ai_client = AIClient()
