import uuid
from typing import Optional, List, Dict
from loguru import logger

from app.database.models.report import Report, StatusEnum
from app.database.models.company import Company
from app.database.repositories.report_repository import ReportRepository
from app.schemas.report import (
    ReportData,
    ReportResponse,
    NewReportCreate,
)
from app.schemas.integration import YandexMetrikaIntegration
from app.services.providers.registry import ProviderRegistry
from app.services.report_assembly.collector import collect_reports
from app.services.report_assembly.merger import union_merge


class ReportService:
    """Сервис для работы с отчетами (новая схема)."""

    def __init__(
        self,
        report_repo: ReportRepository,
        yandex_metrika_integration: Optional[YandexMetrikaIntegration] = None,
        google_analytics_integration: Optional["GoogleAnalyticsIntegration"] = None,
    ):
        self.report_repo = report_repo
        self.provider_registry = ProviderRegistry()
        self.yandex_integration = yandex_metrika_integration
        self.google_integration = google_analytics_integration

    async def create_new_report(
        self, report_data: NewReportCreate, company: Company
    ) -> Report:
        """Создание нового отчета (новая схема)."""
        return await self.report_repo.create_new_report(report_data, company)

    async def _generate_report_data(
        self, report: Report, sources_list: Optional[List[Dict[str, str]]] = None
    ) -> Optional[ReportData]:
        """Генерация данных отчета из одного или нескольких провайдеров.
        Если передан sources_list — используем мульти-провайдерный сбор.
        """
        try:
            if sources_list:
                # Этап 1: параллельный сбор
                collected = await collect_reports(
                    report=report,
                    sources=sources_list,
                    registry=self.provider_registry,
                    yandex_integration=self.yandex_integration,
                    google_integration=self.google_integration,
                )
                if not collected:
                    return None

                # Этап 2: сведение (union)
                return union_merge(collected)

            # Одиночный провайдер
            if self.yandex_integration:
                yandex_provider = self.provider_registry.get_yandex(
                    self.yandex_integration
                )
                return await yandex_provider.generate_report(report)

            # Fallback: если нет Яндекс интеграции, пробуем Google Analytics 4
            google_provider = self.provider_registry.get_google(self.google_integration)
            return await google_provider.generate_report(report)

        except Exception as e:
            logger.error(f"Error generating report data: {str(e)}")
            return None

    async def get_report_by_id(self, report_id: uuid.UUID) -> Optional[Report]:
        """Получение отчета по ID"""
        return await self.report_repo.get_report_by_id(report_id)

    async def retry_report_generation(self, report_id: uuid.UUID) -> bool:
        """Повторная генерация отчета"""
        try:
            # Обновляем статус отчета на proceed и очищаем file_name
            await self.report_repo.update_report_status(report_id, StatusEnum.proceed)
            await self.report_repo.update_report_file(report_id, None)
            return True
        except Exception as e:
            logger.error(f"Error retrying report generation {report_id}: {str(e)}")
            return False

    async def get_reports_by_company(
        self, company_id: uuid.UUID, limit: int = 50
    ) -> list[Report]:
        """Получение отчетов компании"""
        return await self.report_repo.get_reports_by_company(company_id, limit)

    async def update_report_status(
        self, report_id: uuid.UUID, status: StatusEnum
    ) -> Optional[Report]:
        """Обновление статуса отчета"""
        return await self.report_repo.update_report_status(report_id, status)

    async def update_report_conclusion(
        self, report_id: uuid.UUID, conclusion: str, conclusion_status: str = "finish"
    ) -> Optional[Report]:
        """Обновление заключения отчета"""
        return await self.report_repo.update_report_conclusion(
            report_id, conclusion, conclusion_status
        )

    async def set_waiting_for_conclusion(
        self, report_id: uuid.UUID, waiting: bool = True
    ) -> Optional[Report]:
        """Установка флага ожидания заключения"""
        return await self.report_repo.set_waiting_for_conclusion(report_id, waiting)

    async def delete_report(self, report_id: uuid.UUID) -> bool:
        """Удаление отчета"""
        from app.services.s3_service import s3_service

        # Получаем отчет для извлечения имени файла
        report = await self.report_repo.get_report_by_id(report_id)

        # Удаляем отчет из базы данных
        success = await self.report_repo.delete_report(report_id)

        # Если отчет был удален из БД и у него есть файл, удаляем файл из S3
        if success and report and report.file_name:
            await s3_service.delete_report(report.file_name)
            logger.info(f"Deleted report file from S3: {report.file_name}")

        return success

    async def to_response(
        self, report: Report, with_data_preview: bool = False
    ) -> ReportResponse:
        """Преобразование модели отчета в схему ответа"""
        from app.schemas.report import ReportDataPreview, ReportCompareItem

        data_preview = None
        compares = None

        # Генерируем превью данных если запрошено и отчет готов
        if with_data_preview and report.status.value == "finish" and report.file_name:
            try:
                from app.converters.excel import get_report_data_preview

                preview_data = await get_report_data_preview(report.file_name)
                if preview_data:
                    data_preview = ReportDataPreview(
                        headers=preview_data["headers"],
                        rows=preview_data["rows"],
                        total_rows=preview_data["total_rows"],
                    )
            except Exception as e:
                logger.error(
                    f"Failed to generate data preview for {report.file_name}: {str(e)}"
                )

        # Получаем отчеты сравнения если запрошено with_data_preview
        if with_data_preview:
            try:
                report_compares = await self.report_repo.get_compare_reports_by_source(
                    report.id
                )
                compares = [
                    ReportCompareItem(
                        date_1=rc.target_report.date_1,
                        date_2=rc.target_report.date_2,
                        created_at=rc.created_at,
                    )
                    for rc in report_compares
                ]
            except Exception as e:
                logger.error(f"Failed to get compare reports for {report.id}: {str(e)}")

        return ReportResponse(
            id=report.id,
            company_id=report.company_id,
            created_at=report.created_at,
            status=report.status.value,
            file_name=report.file_name,
            data_preview=data_preview,
            source=report.source,
            date_1=report.date_1,
            date_2=report.date_2,
            # Метрики и атрибуты
            goals=report.goals or [],
            selected_metrics=report.selected_metrics or [],
            selected_attributes=report.selected_attributes or [],
            additional_metrics=report.additional_metrics,
            # Дополнительные поля
            compare_date_1=report.compare_date_1,
            compare_date_2=report.compare_date_2,
            conclusion=report.conclusion,
            conclusion_status=(
                report.conclusion_status.value if report.conclusion_status else None
            ),
            user_waiting_for_conclusion=report.user_waiting_for_conclusion,
            cpa_goal=report.cpa_goal,
            cpo_goal=report.cpo_goal,
            is_compared=report.is_compared,
            compares=compares,
        )
