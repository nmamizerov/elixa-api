import uuid
import asyncio
from loguru import logger
from typing import Optional, List, Dict

from app.database.repositories.report_repository import ReportRepository
from app.database.models.report import StatusEnum
from app.database.config import SessionLocal
from app.services.report_service import ReportService
from app.services.conclusion_service import ConclusionService
from app.core.utils import save_report_to_excel
from app.schemas.integration import YandexMetrikaIntegration, GoogleAnalyticsIntegration


class BackgroundTaskService:
    """Сервис для обработки фоновых задач"""

    def __init__(self):
        self.running_tasks = set()

    async def process_report_generation(
        self,
        report_id: uuid.UUID,
        yandex_metrika_integration: Optional[YandexMetrikaIntegration],
        google_analytics_integration: Optional[GoogleAnalyticsIntegration],
        sources_list: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Фоновая задача для генерации отчета"""
        task_id = f"report_{report_id}"

        if task_id in self.running_tasks:
            logger.warning(f"Task {task_id} is already running")
            return

        self.running_tasks.add(task_id)

        try:
            # Получаем сессию базы данных
            async with SessionLocal() as session:
                try:
                    report_repo = ReportRepository(session)
                    report_service = ReportService(
                        report_repo,
                        yandex_metrika_integration=yandex_metrika_integration,
                        google_analytics_integration=google_analytics_integration,
                    )

                    # Получаем отчет из базы
                    report = await report_repo.get_report_by_id(report_id)
                    if not report:
                        logger.error(f"Report {report_id} not found")
                        return

                    # Используем компанию из relationship отчета
                    company = report.company
                    if not company:
                        logger.error(f"Company {report.company_id} not found")
                        await report_repo.update_report_status(
                            report_id, StatusEnum.failed
                        )
                        return

                    # Генерируем данные отчета
                    report_data = await report_service._generate_report_data(
                        report, sources_list=sources_list
                    )

                    if report_data:
                        # Сохраняем отчет в Excel файл
                        file_name = await save_report_to_excel(
                            report_data, f"report_{report.source}"
                        )

                        # Обновляем статус отчета
                        await report_repo.update_report_file(report.id, file_name)
                        await report_repo.update_report_status(
                            report.id, StatusEnum.finish
                        )

                        logger.info(f"Report {report_id} generated successfully")

                        if not report.is_compared:
                            self.start_conclusion_generation(report_id)
                    else:
                        # Ошибка при генерации данных
                        await report_repo.update_report_status(
                            report.id, StatusEnum.failed
                        )
                        logger.error(f"Failed to generate data for report {report_id}")

                except Exception as e:
                    logger.error(f"Error processing report {report_id}: {str(e)}")
                    # Обновляем статус на ошибку
                    async with SessionLocal() as error_session:
                        try:
                            error_repo = ReportRepository(error_session)
                            await error_repo.update_report_status(
                                report_id, StatusEnum.failed
                            )
                        except Exception as inner_e:
                            logger.error(
                                f"Failed to update report status: {str(inner_e)}"
                            )

        except Exception as e:
            logger.error(
                f"Critical error in background task for report {report_id}: {str(e)}"
            )
        finally:
            self.running_tasks.discard(task_id)

    def start_report_generation(
        self,
        report_id: uuid.UUID,
        yandex_metrika_integration: Optional[YandexMetrikaIntegration],
        google_analytics_integration: Optional[GoogleAnalyticsIntegration] = None,
        sources_list: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Запуск фоновой задачи для генерации отчета"""
        try:
            # Создаем задачу в event loop
            loop = asyncio.get_event_loop()
            task = loop.create_task(
                self.process_report_generation(
                    report_id,
                    yandex_metrika_integration,
                    google_analytics_integration,
                    sources_list,
                )
            )

            # Добавляем callback для логирования завершения
            def task_done_callback(task):
                if task.exception():
                    logger.error(f"Background task failed: {task.exception()}")
                else:
                    logger.info(f"Background task completed successfully")

            task.add_done_callback(task_done_callback)

        except Exception as e:
            logger.error(f"Failed to start background task: {str(e)}")

    async def process_conclusion_generation(self, report_id: uuid.UUID) -> None:
        """Фоновая задача для генерации заключения отчета"""
        task_id = f"conclusion_{report_id}"

        if task_id in self.running_tasks:
            logger.warning(f"Task {task_id} is already running")
            return

        self.running_tasks.add(task_id)

        # Получаем сессию базы данных
        async with SessionLocal() as session:
            report_repo = ReportRepository(session)
            conclusion_service = ConclusionService(report_repo)

            # Генерируем заключение
            conclusion = await conclusion_service.generate_conclusion(report_id)

            if conclusion:
                logger.info(f"Conclusion generated successfully for report {report_id}")
            else:
                logger.error(f"Failed to generate conclusion for report {report_id}")

            self.running_tasks.discard(task_id)

    def start_conclusion_generation(self, report_id: uuid.UUID) -> None:
        """Запуск фоновой задачи для генерации заключения отчета"""
        # Создаем задачу в event loop
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.process_conclusion_generation(report_id))

        # Добавляем callback для логирования завершения
        def task_done_callback(task):
            if task.exception():
                logger.error(f"Conclusion generation task failed: {task.exception()}")
            else:
                logger.info(f"Conclusion generation task completed successfully")

        task.add_done_callback(task_done_callback)


# Создаем единственный экземпляр сервиса
background_task_service = BackgroundTaskService()
