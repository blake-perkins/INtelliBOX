"""Configuration management using Pydantic settings."""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite:///./data/emailtools.db"

    # OpenAI API
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_retries: int = 3
    openai_timeout: int = 60

    # Email SMTP Configuration
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool = True

    # Report Configuration
    report_from: str
    report_recipients: str  # Comma-separated email addresses
    report_time: str = "06:00"  # HH:MM format
    timezone: str = "America/New_York"
    program_news_days: int = 7

    # Logging
    log_level: str = "INFO"

    @field_validator("report_recipients")
    @classmethod
    def parse_recipients(cls, v: str) -> str:
        """Validate report_recipients is comma-separated email addresses."""
        if not v or not v.strip():
            raise ValueError("report_recipients cannot be empty")
        return v

    def get_recipients_list(self) -> List[str]:
        """Return report_recipients as a list of email addresses."""
        return [email.strip() for email in self.report_recipients.split(",")]

    @field_validator("report_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate report_time is in HH:MM format."""
        try:
            hour, minute = v.split(":")
            if not (0 <= int(hour) < 24 and 0 <= int(minute) < 60):
                raise ValueError
            return v
        except (ValueError, AttributeError):
            raise ValueError("report_time must be in HH:MM format (e.g., 06:00)")


# Global settings instance
settings = Settings()
