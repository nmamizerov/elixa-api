from typing import List, Dict, Optional, Literal
from loguru import logger

from app.database.models.report import Report
from app.schemas.report import ReportData
from app.core.constants import (
    FREE_METRICS,
    FREE_ATTRIBUTES_MAPPING,
    FREE_METRIC_NAMES,
)
from .base import BaseReportGenerator


class FreeReportGenerator(BaseReportGenerator):
    """Генератор отчетов для бесплатного трафика (органика)"""

    def __init__(self, metrika_client, yandex_metrika_integration):
        super().__init__(metrika_client, yandex_metrika_integration)
        self.include_ad: bool = False

    def get_base_metrics(self) -> List[str]:
        """Получение базовых метрик для бесплатного трафика"""
        return FREE_METRICS.copy()

    def get_attributes_mapping(self) -> Dict[str, str]:
        """Получение соответствия атрибутов метрикам для бесплатного трафика"""
        return FREE_ATTRIBUTES_MAPPING.copy()

    def get_metric_names(self) -> Dict[str, str]:
        """Получение русских названий метрик для бесплатного трафика"""
        return FREE_METRIC_NAMES.copy()

    def get_traffic_type(self) -> Literal["paid", "free"]:
        """Тип трафика - бесплатный"""
        return "free"

    def get_main_dimensions(self) -> List[str]:
        """Получение основных измерений - источники трафика"""
        return ["ym:s:lastSignTrafficSource"]

    def get_detail_dimensions(self) -> List[str]:
        """Получение детальных измерений - платформы внутри источников"""
        return ["ym:s:lastSignSourceEngine"]

    def _get_main_header_name(self) -> str:
        """Название для первого столбца"""
        return "Источник трафика"

    def _get_main_filters(self) -> Optional[str]:
        """Фильтры для исключения рекламного трафика (если include_ad=False)"""
        return None if self.include_ad else "ym:s:lastSignTrafficSource!='ad'"

    def _build_detail_filter(self, main_id: str) -> Optional[str]:
        """Построение фильтра для детального уровня"""
        return f"ym:s:lastSignTrafficSource=='{main_id}'"

    async def generate_report(self, report: Report) -> Optional[ReportData]:
        """Генерация отчета для бесплатного трафика"""
        await self._log_generation_start(report)

        try:
            # Для source == "all" включаем рекламный трафик в разрезе бесплатного отчета
            self.include_ad = report.source == "all"

            # Получаем метрики и названия целей
            goal_metrics, goal_names = await self._get_goal_metrics_and_names(report)
            logger.info(f"🔹 Found {len(goal_metrics)} goal metrics")

            # Формируем список выбранных метрик
            selected_metrics = self._build_selected_metrics(report, goal_metrics)
            logger.info(f"🔹 Total metrics to fetch: {len(selected_metrics)}")

            # Обрабатываем иерархические данные
            headers, rows = await self._process_hierarchical_data(
                report, selected_metrics, goal_names
            )

            logger.info(
                f"🔹 Generated report with {len(headers)} columns and {len(rows)} rows"
            )

            result = ReportData(headers=headers, rows=rows, meta_data=[])

            await self._log_generation_complete(report, True)
            return result

        except Exception as e:
            logger.error(f"🔹 Error generating free report: {str(e)}")
            await self._log_generation_complete(report, False)
            return None
