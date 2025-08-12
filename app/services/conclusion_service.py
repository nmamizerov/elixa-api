import uuid
from typing import Optional
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from app.core.config import settings
from app.database.models.report import Report, ConclusionStatusEnum
from app.database.repositories.report_repository import ReportRepository
from app.agent.prompts.generate_conclusion import GENERATE_CONCLUSION_PROMPT
from app.converters.excel import get_report_data_preview


class ConclusionService:
    """Сервис для генерации выводов по отчетам"""

    def __init__(self, report_repo: ReportRepository):
        self.report_repo = report_repo
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY,
            max_tokens=4000,
        )

    async def generate_conclusion(self, report_id: uuid.UUID) -> Optional[str]:
        """Генерация заключения для отчета"""
        try:
            # Получаем отчет из базы данных
            report = await self.report_repo.get_report_by_id(report_id)
            if not report:
                logger.error(f"Report {report_id} not found")
                return None

            # Проверяем, что отчет готов и у него есть файл
            if not report.file_name:
                logger.error(f"Report {report_id} has no file")
                return None

            # Устанавливаем статус "в процессе"
            await self.report_repo.update_report_conclusion(
                report_id, "", ConclusionStatusEnum.proceed.value
            )

            # Получаем данные отчета
            report_data = await self._get_report_data(report.file_name)
            if not report_data:
                await self.report_repo.update_report_conclusion(
                    report_id, "", ConclusionStatusEnum.failed.value
                )
                return None

            # Формируем метаданные отчета
            report_metadata = self._format_report_metadata(report)

            # Генерируем заключение через LLM
            conclusion = await self._generate_with_llm(report_metadata, report_data)

            if conclusion:
                # Сохраняем заключение в базе данных
                await self.report_repo.update_report_conclusion(
                    report_id, conclusion, ConclusionStatusEnum.finish.value
                )
                logger.info(f"Conclusion generated successfully for report {report_id}")
                return conclusion
            else:
                await self.report_repo.update_report_conclusion(
                    report_id, "", ConclusionStatusEnum.failed.value
                )
                return None

        except Exception as e:
            logger.error(
                f"Error generating conclusion for report {report_id}: {str(e)}"
            )
            await self.report_repo.update_report_conclusion(
                report_id, "", ConclusionStatusEnum.failed.value
            )
            return None

    async def _get_report_data(self, file_name: str) -> Optional[str]:
        """Получение данных отчета из файла"""
        try:
            # Используем функцию превью для получения данных
            preview_data = await get_report_data_preview(file_name)
            if not preview_data:
                return None

            # Форматируем данные в читаемый вид
            headers = preview_data.get("headers", [])
            rows = preview_data.get("rows", [])
            total_rows = preview_data.get("total_rows", 0)

            # Создаем текстовое представление данных
            data_text = f"Общее количество строк в отчете: {total_rows}\n\n"
            data_text += f"Заголовки: {', '.join(headers)}\n\n"
            data_text += "Первые строки данных:\n"

            for i, row in enumerate(rows[:20], 1):  # Берем только первые 20 строк
                data_text += f"{i}. {' | '.join(str(cell) for cell in row)}\n"

            if len(rows) > 20:
                data_text += f"... и еще {len(rows) - 20} строк\n"

            return data_text

        except Exception as e:
            logger.error(f"Error reading report data from {file_name}: {str(e)}")
            return None

    def _format_report_metadata(self, report: Report) -> str:
        """Форматирование метаданных отчета"""
        metadata = f"""
Период анализа: с {report.date_1} по {report.date_2}
Источник данных: {report.source}
Дата создания отчета: {report.created_at.strftime('%Y-%m-%d %H:%M')}
"""

        if report.goals:
            metadata += f"Цели: {', '.join(report.goals)}\n"

        if report.selected_metrics:
            metadata += f"Выбранные метрики: {', '.join(report.selected_metrics)}\n"

        if report.selected_attributes:
            metadata += f"Группировки: {', '.join(report.selected_attributes)}\n"

        if report.additional_metrics:
            metadata += f"Дополнительные метрики: {report.additional_metrics}\n"

        if report.compare_date_1 and report.compare_date_2:
            metadata += f"Период сравнения: с {report.compare_date_1} по {report.compare_date_2}\n"

        if report.cpa_goal:
            metadata += f"Целевой CPA: {report.cpa_goal}\n"

        if report.cpo_goal:
            metadata += f"Целевой CPO: {report.cpo_goal}\n"

        return metadata.strip()

    async def _generate_with_llm(
        self, report_metadata: str, report_data: str
    ) -> Optional[str]:
        """Генерация заключения с помощью LLM"""
        try:
            # Подготавливаем промпт
            prompt = GENERATE_CONCLUSION_PROMPT.format(
                report_metadata=report_metadata, report_data=report_data
            )

            # Формируем сообщения для LLM
            messages = [
                SystemMessage(
                    content="Ты - эксперт-аналитик по веб-аналитике. Анализируй данные и давай конкретные рекомендации."
                ),
                HumanMessage(content=prompt),
            ]

            # Получаем ответ от LLM
            response = await self.llm.ainvoke(messages)

            if response and response.content:
                logger.info("LLM conclusion generated successfully")
                return response.content.strip()
            else:
                logger.error("Empty response from LLM")
                return None

        except Exception as e:
            logger.error(f"Error generating conclusion with LLM: {str(e)}")
            return None

    async def retry_conclusion_generation(self, report_id: uuid.UUID) -> Optional[str]:
        """Повторная попытка генерации заключения"""
        logger.info(f"Retrying conclusion generation for report {report_id}")
        return await self.generate_conclusion(report_id)
