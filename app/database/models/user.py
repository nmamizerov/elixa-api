import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    DateTime,
    func,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.models.base import Base

# Forward declaration for type hinting
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.models.company import Company, CompanyUser
    from app.database.models.chat import Chat


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    current_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    companies: Mapped[list["Company"]] = relationship(
        "Company", back_populates="user", cascade="all, delete-orphan"
    )
    chats: Mapped[list["Chat"]] = relationship(
        "Chat", back_populates="user", cascade="all, delete-orphan"
    )
    company_users: Mapped[list["CompanyUser"]] = relationship(
        "CompanyUser", back_populates="user", cascade="all, delete-orphan"
    )
    onboarded: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
