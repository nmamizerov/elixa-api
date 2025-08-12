import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
    func,
    String,
    Boolean,
    Enum,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database.models.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.models.company import Company
    from app.database.models.chat import Chat


class StatusEnum(enum.Enum):
    proceed = "proceed"
    finish = "finish"
    failed = "failed"


class ConclusionStatusEnum(enum.Enum):
    proceed = "proceed"
    finish = "finish"
    failed = "failed"
    waiting = "waiting"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    goals: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    selected_metrics: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    selected_attributes: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    additional_metrics: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="paid", server_default="paid")
    date_1: Mapped[str | None] = mapped_column(String)
    date_2: Mapped[str | None] = mapped_column(String)
    compare_date_1: Mapped[str | None] = mapped_column(String)
    compare_date_2: Mapped[str | None] = mapped_column(String)
    status: Mapped[StatusEnum] = mapped_column(
        Enum(StatusEnum), default=StatusEnum.proceed, server_default="proceed"
    )
    file_name: Mapped[str | None] = mapped_column(String)
    conclusion: Mapped[str | None] = mapped_column(Text)
    conclusion_status: Mapped[ConclusionStatusEnum | None] = mapped_column(
        Enum(ConclusionStatusEnum), default=ConclusionStatusEnum.waiting
    )
    user_waiting_for_conclusion: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    cpa_goal: Mapped[str | None] = mapped_column(String)
    cpo_goal: Mapped[str | None] = mapped_column(String)
    is_compared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="reports")
    chats: Mapped[list["Chat"]] = relationship(
        "Chat", back_populates="report", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Report(id={self.id}, status={self.status})>"


class ReportCompare(Base):
    """Модель для отслеживания связей между исходными отчетами и отчетами сравнения"""

    __tablename__ = "report_compares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    target_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )

    # Relationships
    source_report: Mapped["Report"] = relationship(
        "Report", foreign_keys=[source_report_id], lazy="select"
    )
    target_report: Mapped["Report"] = relationship(
        "Report", foreign_keys=[target_report_id], lazy="select"
    )

    def __repr__(self):
        return f"<ReportCompare(source={self.source_report_id}, target={self.target_report_id})>"
