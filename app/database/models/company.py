import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    func,
    String,
    BigInteger,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.models.user import User
    from app.database.models.report import Report
    from app.database.models.integration import (
        YandexMetrikaIntegration,
        GoogleAnalyticsIntegration,
    )


class CompanyUserRole(enum.Enum):
    owner = "owner"
    member = "member"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="companies")
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="company", cascade="all, delete-orphan"
    )
    company_users: Mapped[list["CompanyUser"]] = relationship(
        "CompanyUser", back_populates="company", cascade="all, delete-orphan"
    )
    yandex_metrika_integrations: Mapped[list["YandexMetrikaIntegration"]] = (
        relationship(
            "YandexMetrikaIntegration",
            back_populates="company",
            cascade="all, delete-orphan",
        )
    )
    google_analytics_integrations: Mapped[list["GoogleAnalyticsIntegration"]] = (
        relationship(
            "GoogleAnalyticsIntegration",
            back_populates="company",
            cascade="all, delete-orphan",
        )
    )


class CompanyUser(Base):
    """Связь пользователей с компаниями и их роли"""

    __tablename__ = "company_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    role: Mapped[CompanyUserRole] = mapped_column(
        Enum(CompanyUserRole), default=CompanyUserRole.member
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="company_users")
    company: Mapped["Company"] = relationship("Company", back_populates="company_users")

    # Уникальная связь пользователь-компания
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="unique_user_company"),
    )
