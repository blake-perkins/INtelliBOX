"""SQLAlchemy ORM models for EmailTools."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Email(Base):
    """Email record with metadata and content."""

    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    to_addresses: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array as TEXT
    cc_addresses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array as TEXT
    received_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_eml_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    actions: Mapped[List["Action"]] = relationship(
        "Action",
        back_populates="email",
        cascade="all, delete-orphan"
    )
    processing_logs: Mapped[List["ProcessingLog"]] = relationship(
        "ProcessingLog",
        back_populates="email",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Email(id={self.id}, subject='{self.subject[:50]}', from='{self.from_address}')>"


class Action(Base):
    """Action item extracted from an email."""

    __tablename__ = "actions"
    __table_args__ = (
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="check_priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_ai_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    email: Mapped["Email"] = relationship("Email", back_populates="actions")
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment",
        back_populates="action",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Action(id={self.id}, title='{self.title[:50]}', priority='{self.priority}')>"

    @property
    def is_assigned(self) -> bool:
        """Check if this action has any assignments."""
        return len(self.assignments) > 0


class Assignment(Base):
    """Assignment of an action to a team member."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed')",
            name="check_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="assigned",
        nullable=False,
        index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    action: Mapped["Action"] = relationship("Action", back_populates="assignments")

    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, action_id={self.action_id}, to='{self.assigned_to}', status='{self.status}')>"


class ProcessingLog(Base):
    """Audit trail for email processing events."""

    __tablename__ = "processing_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failure', 'warning')",
            name="check_log_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON as TEXT
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    # Relationships
    email: Mapped[Optional["Email"]] = relationship("Email", back_populates="processing_logs")

    def __repr__(self) -> str:
        return f"<ProcessingLog(id={self.id}, event='{self.event_type}', status='{self.status}')>"


class ProgramNewsCache(Base):
    """Cached program news summary to avoid excessive AI API calls."""

    __tablename__ = "program_news_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    days_covered: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    email_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_email_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    def __repr__(self) -> str:
        return f"<ProgramNewsCache(id={self.id}, generated_at='{self.generated_at}')>"


class Settings(Base):
    """Application settings for priority rules and configuration."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded value
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Settings(key='{self.key}', value='{self.value[:50]}')>"


class ReportCache(Base):
    """Cache for generated reports to avoid expensive AI calls."""

    __tablename__ = "report_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded report
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    def __repr__(self) -> str:
        return f"<ReportCache(id={self.id}, generated_at='{self.generated_at}')>"
