import uuid
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    func,
    String,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.database.models.base import Base
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from app.database.models.user import User
    from app.database.models.report import Report


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255), default="Новый чат")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="chats")
    report: Mapped["Report | None"] = relationship("Report", back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(50))  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    path: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    parent: Mapped["Message | None"] = relationship(
        "Message", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Message"]] = relationship(
        "Message", back_populates="parent", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект Message в словарь для JSON сериализации"""
        return {
            "id": str(self.id),
            "chat_id": str(self.chat_id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "role": self.role,
            "content": self.content,
            "data": self.data,
            "path": self.path or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
