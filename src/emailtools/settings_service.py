"""Service for managing application settings."""

import json
from typing import Any, Optional

from .database import get_session
from .models import Settings


class SettingsService:
    """Service for reading and writing application settings."""

    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """Get a setting value by key, return default if not found."""
        with get_session() as session:
            setting = session.query(Settings).filter_by(key=key).first()
            if not setting:
                return default

            # Try to parse as JSON, fall back to string
            try:
                return json.loads(setting.value)
            except (json.JSONDecodeError, ValueError):
                return setting.value

    @staticmethod
    def set_setting(key: str, value: Any, description: Optional[str] = None) -> None:
        """Set a setting value by key."""
        with get_session() as session:
            setting = session.query(Settings).filter_by(key=key).first()

            # Convert value to JSON string
            json_value = json.dumps(value) if not isinstance(value, str) else value

            if setting:
                setting.value = json_value
                if description is not None:
                    setting.description = description
            else:
                setting = Settings(
                    key=key,
                    value=json_value,
                    description=description
                )
                session.add(setting)

            session.commit()

    @staticmethod
    def get_all_settings() -> dict[str, Any]:
        """Get all settings as a dictionary."""
        with get_session() as session:
            settings = session.query(Settings).all()
            result = {}
            for setting in settings:
                try:
                    result[setting.key] = json.loads(setting.value)
                except (json.JSONDecodeError, ValueError):
                    result[setting.key] = setting.value
            return result

    DEFAULT_CATEGORIES = [
        {"name": "RFI",                  "description": "Request for Information requiring a data or document response"},
        {"name": "data_call",            "description": "Request to provide specific data, metrics, or a report"},
        {"name": "stakeholder_request",  "description": "Request from an executive, client, or external stakeholder"},
        {"name": "meeting_action",       "description": "Action item assigned during or following a meeting"},
        {"name": "deliverable",          "description": "A work product or artifact that must be produced and submitted"},
        {"name": "other",                "description": "Any action item that does not fit the above categories"},
    ]

    DEFAULT_TIMEZONE = "America/Chicago"

    @staticmethod
    def get_timezone() -> str:
        """Get the configured timezone (IANA name), defaulting to America/Chicago."""
        return SettingsService.get_setting('timezone', SettingsService.DEFAULT_TIMEZONE)

    @staticmethod
    def get_priority_config() -> dict:
        """Get priority-related configuration settings."""
        return {
            'days_threshold': SettingsService.get_setting('priority_days_threshold', 5),
            'high_senders': SettingsService.get_setting('priority_high_senders', []),
            'high_keywords': SettingsService.get_setting('priority_high_keywords', []),
            'default_priority': SettingsService.get_setting('priority_default', 'medium')
        }

    @staticmethod
    def get_ai_config() -> dict:
        """Get AI processing configuration settings."""
        return {
            'confidence_threshold': SettingsService.get_setting('ai_confidence_threshold', 0.5),
            'categories': SettingsService.get_setting('ai_categories', SettingsService.DEFAULT_CATEGORIES),
        }

    @staticmethod
    def format_categories_for_prompt(categories: list) -> str:
        """Format category list into a prompt-ready bulleted string."""
        return '\n'.join(f'   - "{c["name"]}": {c["description"]}' for c in categories)

    @staticmethod
    def update_last_sync_time() -> None:
        """Record the current UTC time as the last sync timestamp."""
        from emailtools.utils.datetime_utils import utcnow
        SettingsService.set_setting('last_sync_time', utcnow().isoformat())

    @staticmethod
    def parse_categories_text(text: str) -> list:
        """
        Parse a categories textarea value into a list of {name, description} dicts.

        Each line should be "name: description". Lines without a colon or with an
        empty name/description are skipped. If the description itself contains colons,
        only the first colon is used as the separator (partition behaviour).
        Returns DEFAULT_CATEGORIES if no valid lines are found.
        """
        categories = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if ':' not in line:
                continue
            name, _, description = line.partition(':')
            name = name.strip()
            description = description.strip()
            if name and description:
                categories.append({"name": name, "description": description})
        return categories if categories else SettingsService.DEFAULT_CATEGORIES

    @staticmethod
    def get_insights_prompt() -> str:
        """Return the custom insights prompt, or the hardcoded default."""
        from emailtools.ai.prompts import REPORT_INSIGHTS_PROMPT
        return SettingsService.get_setting("insights_prompt", REPORT_INSIGHTS_PROMPT)

    @staticmethod
    def delete_setting(key: str) -> None:
        """Remove a setting row entirely (resets to code default)."""
        with get_session() as session:
            setting = session.query(Settings).filter_by(key=key).first()
            if setting:
                session.delete(setting)
                session.commit()
