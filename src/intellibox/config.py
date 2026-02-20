"""Configuration management using Pydantic settings."""

from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite:///./data/intellibox.db"

    # PostgreSQL connection pool settings (ignored for SQLite)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    @property
    def is_postgres(self) -> bool:
        """Check if the database backend is PostgreSQL."""
        return self.database_url.startswith("postgresql")

    # OpenAI API
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
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

    # AI Processing
    ai_batch_size: int = 10
    ai_batch_delay: float = 2.0  # seconds between batches

    # Logging
    log_level: str = "INFO"

    # Team members (comma-separated list for assignment dropdown)
    team_members: str = ""

    def get_team_members(self) -> list[str]:
        """Get list of team members from config."""
        if not self.team_members:
            return []
        return [member.strip() for member in self.team_members.split(",") if member.strip()]

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
