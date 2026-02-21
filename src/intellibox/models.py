"""SQLAlchemy ORM models for INtelliBOX."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from intellibox.utils.datetime_utils import utcnow


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
    also_received_from: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of {address, name}
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
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
        default=utcnow,
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
        default=utcnow,
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
        default=utcnow,
        nullable=False,
        index=True
    )

    # Relationships
    email: Mapped[Optional["Email"]] = relationship("Email", back_populates="processing_logs")

    def __repr__(self) -> str:
        return f"<ProcessingLog(id={self.id}, event='{self.event_type}', status='{self.status}')>"


class AuditLog(Base):
    """Audit trail for user write operations."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user='{self.user}', "
            f"action='{self.action}', resource='{self.resource_type}:{self.resource_id}')>"
        )


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
        default=utcnow,
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
        default=utcnow,
        onupdate=utcnow,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Settings(key='{self.key}', value='{self.value[:50]}')>"


class RosterMember(Base):
    """Program roster member for assignment dropdown."""

    __tablename__ = "roster"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<RosterMember(id={self.id}, name='{self.full_name}', email='{self.email}')>"


class ReportCache(Base):
    """Cache for generated reports to avoid expensive AI calls."""

    __tablename__ = "report_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded report
    generated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True
    )

    def __repr__(self) -> str:
        return f"<ReportCache(id={self.id}, generated_at='{self.generated_at}')>"


class User(Base):
    """Application user (local or OIDC-provisioned)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="check_user_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # NULL for OIDC-only
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    oidc_sub: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    roster_member_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roster.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    # Relationships
    roster_member: Mapped[Optional["RosterMember"]] = relationship("RosterMember")
    sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class UserSession(Base):
    """Server-side session storage (signed cookie holds only session_id)."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<UserSession(id='{self.id}', user_id={self.user_id})>"


class KnowledgeDocument(Base):
    """Program document uploaded to the knowledge base for RAG context."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf, docx, txt
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        String(20), default="success", nullable=False
    )  # success, failed, partial
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True
    )

    # Relationships
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    @property
    def file_size_display(self) -> str:
        """Human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    @property
    def text_length(self) -> int:
        return len(self.extracted_text) if self.extracted_text else 0

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, filename='{self.filename}')>"


class KnowledgeChunk(Base):
    """Chunk of a knowledge document with its OpenAI embedding vector."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of floats

    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(id={self.id}, doc_id={self.document_id}, idx={self.chunk_index})>"
