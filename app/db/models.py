import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Session")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-3-5-sonnet-20241022")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    messages: Mapped[list["MessageModel"]] = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan", order_by="MessageModel.created_at"
    )

class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=True, default="")
    tool_calls: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    screenshots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="messages")
