"""OpenAI GPT-4 client for email analysis."""

import json
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError

from emailtools.ai.prompts import ACTION_EXTRACTION_PROMPT, PROGRAM_NEWS_PROMPT, REPORT_INSIGHTS_PROMPT, STRUCTURED_PROGRAM_NEWS_PROMPT, SYSTEM_PROMPT
from emailtools.config import settings
from emailtools.models import Action, Email
from emailtools.utils.logging import logger
from emailtools.priority_rules import PriorityRuleEngine


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

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,  # Balanced for structured output
                max_tokens=800,
                timeout=self.timeout
            )

            raw_response = response.choices[0].message.content.strip()
            logger.debug(f"Structured program news response: {raw_response[:200]}...")

            # Parse JSON response
            try:
                clean_json = strip_markdown_json(raw_response)
                structured_news = json.loads(clean_json)
                logger.info("Structured program news generated successfully")
                return structured_news

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse structured news JSON: {e}")
                logger.error(f"Raw response: {raw_response}")
                # Return fallback structure
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
        actions: List,
        emails: List[Email],
        days: int = 7
    ) -> Dict:
        """
        Generate comprehensive insights for the report dashboard.

        Args:
            actions: List of Action objects to analyze
            emails: List of recent Email objects
            days: Number of days covered

        Returns:
            Dictionary with structured insights
        """
        if not actions and not emails:
            return {
                "executive_summary": "No recent activity to report.",
                "trends": {},
                "category_insights": [],
                "urgent_items": [],
                "bottlenecks": "Insufficient data for analysis.",
                "recommendations": []
            }

        # Calculate metrics
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        week_from_now = now + timedelta(days=7)

        total_actions = len(actions)
        high_priority_count = sum(1 for a in actions if a.priority == "high")
        medium_priority_count = sum(1 for a in actions if a.priority == "medium")
        low_priority_count = sum(1 for a in actions if a.priority == "low")

        overdue_count = sum(1 for a in actions if a.due_date and a.due_date < now)
        due_this_week_count = sum(
            1 for a in actions
            if a.due_date and now <= a.due_date <= week_from_now
        )

        # Category breakdown
        category_counts = {}
        for action in actions:
            cat = action.category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

        category_breakdown = "\n".join(
            f"- {cat}: {count}" for cat, count in sorted(
                category_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        )

        # Email summaries (limit to 15 most recent)
        email_summaries = []
        for email in emails[:15]:
            summary = f"- From {email.from_address}: {email.subject}"
            email_summaries.append(summary)
        email_summaries_text = "\n".join(email_summaries) if email_summaries else "No recent emails"

        # Format the prompt
        prompt = REPORT_INSIGHTS_PROMPT.format(
            total_actions=total_actions,
            high_priority_count=high_priority_count,
            medium_priority_count=medium_priority_count,
            low_priority_count=low_priority_count,
            overdue_count=overdue_count,
            due_this_week_count=due_this_week_count,
            category_breakdown=category_breakdown or "- No categories",
            days=days,
            email_summaries=email_summaries_text
        )

        try:
            logger.info(f"Generating report insights from {total_actions} actions and {len(emails)} emails")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,  # Balanced for insights
                max_tokens=1000,
                timeout=self.timeout
            )

            raw_response = response.choices[0].message.content.strip()
            logger.debug(f"Report insights response: {raw_response[:200]}...")

            # Parse JSON response
            try:
                clean_json = strip_markdown_json(raw_response)
                insights = json.loads(clean_json)
                logger.info("Report insights generated successfully")
                return insights

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse insights JSON: {e}")
                logger.error(f"Raw response: {raw_response}")
                # Return fallback structure
                return {
                    "executive_summary": "Unable to generate insights at this time.",
                    "trends": {},
                    "category_insights": [],
                    "urgent_items": [],
                    "bottlenecks": "Error parsing AI response.",
                    "recommendations": []
                }

        except Exception as e:
            logger.error(f"Failed to generate report insights: {e}")
            return {
                "executive_summary": f"Error generating insights: {str(e)[:100]}",
                "trends": {},
                "category_insights": [],
                "urgent_items": [],
                "bottlenecks": "",
                "recommendations": []
            }


# Singleton instance
ai_client = AIClient()
