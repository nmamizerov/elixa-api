import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models.report import Report, StatusEnum, ReportCompare
from app.database.models.company import Company
from app.schemas.report import (
    ReportCreate,
    NewReportCreate,
)


class ReportRepository:
    """Репозиторий для работы с отчетами"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_report(
        self, report_data: ReportCreate, company: Company
    ) -> Report:
        """Создание нового отчета"""
        report = Report(
            company_id=company.id,
            date_1=report_data.state.date_1,
            date_2=report_data.state.date_2,
            goals=report_data.state.selected_goals,
            selected_metrics=report_data.state.selected_metrics,
            selected_attributes=report_data.state.attributes,
            source=report_data.state.source,
            additional_metrics=report_data.state.additional_metrics,
            status=StatusEnum.proceed,
            user_waiting_for_conclusion=False,
            cpa_goal=report_data.state.cpa_goal,
            cpo_goal=report_data.state.cpo_goal,
            compare_date_1=report_data.state.compare_date_1,
            compare_date_2=report_data.state.compare_date_2,
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def create_new_report(
        self, report_data: NewReportCreate, company: Company
    ) -> Report:
        """Создание нового отчета с новой схемой данных"""
        req = report_data.request_data
        # Новая модель: compareEnabled отсутствует — используем даты как есть
        compare_date_1 = req.compare_date_1
        compare_date_2 = req.compare_date_2

        report = Report(
            company_id=company.id,
            date_1=req.date_1,
            date_2=req.date_2,
            goals=req.goals,
            selected_metrics=req.metrics,
            selected_attributes=req.attributes,
            source=req.traffic_kind,
            additional_metrics="",
            status=StatusEnum.proceed,
            user_waiting_for_conclusion=False,
            cpa_goal=req.cpaGoalId,
            cpo_goal=req.cpoGoalId,
            compare_date_1=compare_date_1,
            compare_date_2=compare_date_2,
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_report_by_id(self, report_id: uuid.UUID) -> Optional[Report]:
        """Получение отчета по ID"""
        result = await self.db.execute(
            select(Report)
            .where(Report.id == report_id)
            .options(selectinload(Report.company))
        )
        return result.scalar_one_or_none()

    async def get_reports_by_company(
        self, company_id: uuid.UUID, limit: int = 50
    ) -> List[Report]:
        """Получение отчетов компании (исключая отчеты сравнения)"""
        result = await self.db.execute(
            select(Report)
            .where(Report.company_id == company_id, Report.is_compared == False)
            .options(selectinload(Report.company))
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_report_status(
        self, report_id: uuid.UUID, status: StatusEnum
    ) -> Optional[Report]:
        """Обновление статуса отчета"""
        report = await self.get_report_by_id(report_id)
        if report:
            report.status = status
            await self.db.commit()
            await self.db.refresh(report)
        return report

    async def update_report_file(
        self, report_id: uuid.UUID, file_name: str
    ) -> Optional[Report]:
        """Обновление файла отчета"""
        report = await self.get_report_by_id(report_id)
        if report:
            report.file_name = file_name
            await self.db.commit()
            await self.db.refresh(report)
        return report

    async def update_report_conclusion(
        self, report_id: uuid.UUID, conclusion: str, conclusion_status: str = "finish"
    ) -> Optional[Report]:
        """Обновление заключения отчета"""
        from app.database.models.report import ConclusionStatusEnum

        report = await self.get_report_by_id(report_id)
        if report:
            report.conclusion = conclusion
            # Преобразуем строку в enum при необходимости и присваиваем один раз
            if isinstance(conclusion_status, str):
                report.conclusion_status = ConclusionStatusEnum(conclusion_status)
            else:
                report.conclusion_status = conclusion_status
            report.user_waiting_for_conclusion = False
            await self.db.commit()
            await self.db.refresh(report)
        return report

    async def set_waiting_for_conclusion(
        self, report_id: uuid.UUID, waiting: bool = True
    ) -> Optional[Report]:
        """Установка флага ожидания заключения"""
        report = await self.get_report_by_id(report_id)
        if report:
            report.user_waiting_for_conclusion = waiting
            await self.db.commit()
            await self.db.refresh(report)
        return report

    async def delete_report(self, report_id: uuid.UUID) -> bool:
        """Удаление отчета"""
        report = await self.get_report_by_id(report_id)
        if report:
            await self.db.delete(report)
            await self.db.commit()
            return True
        return False

    async def get_pending_reports(self) -> List[Report]:
        """Получение всех отчетов в процессе обработки"""
        result = await self.db.execute(
            select(Report)
            .where(Report.status == StatusEnum.proceed)
            .options(selectinload(Report.company))
            .order_by(Report.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_failed_reports(self) -> List[Report]:
        """Получение всех проваленных отчетов"""
        result = await self.db.execute(
            select(Report)
            .where(Report.status == StatusEnum.failed)
            .options(selectinload(Report.company))
            .order_by(Report.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_existing_compare_report(
        self, original_report: Report, date_1: str, date_2: str
    ) -> Optional[Report]:
        """Поиск существующего отчета сравнения с такими же параметрами"""
        result = await self.db.execute(
            select(Report).where(
                Report.company_id == original_report.company_id,
                Report.is_compared == True,
                Report.date_1 == date_1,
                Report.date_2 == date_2,
                Report.source == original_report.source,
                Report.selected_metrics == original_report.selected_metrics,
                Report.selected_attributes == original_report.selected_attributes,
                Report.goals == original_report.goals,
                Report.cpa_goal == original_report.cpa_goal,
                Report.cpo_goal == original_report.cpo_goal,
                Report.additional_metrics == original_report.additional_metrics,
            )
        )
        return result.scalar_one_or_none()

    async def create_compare_report(
        self, original_report: Report, date_1: str, date_2: str
    ) -> Report:
        """Создание отчета сравнения на основе исходного отчета"""
        compare_report = Report(
            company_id=original_report.company_id,
            date_1=date_1,
            date_2=date_2,
            goals=original_report.goals,
            selected_metrics=original_report.selected_metrics,
            selected_attributes=original_report.selected_attributes,
            source=original_report.source,
            additional_metrics=original_report.additional_metrics,
            status=StatusEnum.proceed,
            user_waiting_for_conclusion=False,
            cpa_goal=original_report.cpa_goal,
            cpo_goal=original_report.cpo_goal,
            compare_date_1=None,
            compare_date_2=None,
            is_compared=True,
        )

        self.db.add(compare_report)
        await self.db.commit()
        await self.db.refresh(compare_report)
        return compare_report

    async def create_report_compare(
        self, source_report_id: uuid.UUID, target_report_id: uuid.UUID
    ) -> ReportCompare:
        """Создание записи о связи между исходным отчетом и отчетом сравнения"""
        report_compare = ReportCompare(
            source_report_id=source_report_id,
            target_report_id=target_report_id,
        )

        self.db.add(report_compare)
        await self.db.commit()
        await self.db.refresh(report_compare)
        return report_compare

    async def get_compare_reports_by_source(
        self, source_report_id: uuid.UUID, limit: int = 1
    ) -> List[ReportCompare]:
        """Получение всех отчетов сравнения для исходного отчета"""
        result = await self.db.execute(
            select(ReportCompare)
            .where(ReportCompare.source_report_id == source_report_id)
            .limit(limit)
            .options(
                selectinload(ReportCompare.source_report),
                selectinload(ReportCompare.target_report),
            )
            .order_by(ReportCompare.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_report_compare(
        self, source_report_id: uuid.UUID, target_report_id: uuid.UUID
    ) -> Optional[ReportCompare]:
        """Получение записи о связи между отчетами"""
        result = await self.db.execute(
            select(ReportCompare).where(
                ReportCompare.source_report_id == source_report_id,
                ReportCompare.target_report_id == target_report_id,
            )
        )
        return result.scalar_one_or_none()
