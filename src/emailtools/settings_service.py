"""Service for managing application settings."""

import json
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from .models import Settings
from .database import get_session


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

    @staticmethod
    def get_priority_config() -> dict:
        """Get priority-related configuration settings."""
        return {
            'days_threshold': SettingsService.get_setting('priority_days_threshold', 5),
            'high_senders': SettingsService.get_setting('priority_high_senders', []),
            'high_keywords': SettingsService.get_setting('priority_high_keywords', []),
            'default_priority': SettingsService.get_setting('priority_default', 'medium')
        }
