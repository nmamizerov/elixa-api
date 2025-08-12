import uuid
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    func,
    BigInteger,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database.models.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.models.company import Company


class YandexMetrikaIntegration(Base):
    """Модель для интеграции с Яндекс.Метрикой"""

    __tablename__ = "yandex_metrika_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    counter_id: Mapped[int] = mapped_column(BigInteger, index=True)
    token: Mapped[str] = mapped_column(Text)  # Будет шифроваться на уровне сервиса

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )
    goals: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    data: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company", back_populates="yandex_metrika_integrations"
    )


class GoogleAnalyticsIntegration(Base):
    """Модель для интеграции с Google Analytics 4 (GA4)."""

    __tablename__ = "google_analytics_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Идентификатор GA4 Property (например, "123456789").
    property_id: Mapped[str] = mapped_column(Text, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    # Резерв для кэшированных данных/метаданных
    data: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company", back_populates="google_analytics_integrations"
    )
