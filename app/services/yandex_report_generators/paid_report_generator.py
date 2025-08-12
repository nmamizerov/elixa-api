from typing import List, Dict, Optional, Literal
from loguru import logger

from app.database.models.report import Report
from app.schemas.report import ReportData
from app.core.constants import (
    PAID_METRICS,
    PAID_ATTRIBUTES_MAPPING,
    PAID_METRIC_NAMES,
)
from .base import BaseReportGenerator


class PaidReportGenerator(BaseReportGenerator):
    """Генератор отчетов для платного трафика (реклама)"""

    def get_base_metrics(self) -> List[str]:
        """Получение базовых метрик для платного трафика"""
        return PAID_METRICS.copy()

    def get_attributes_mapping(self) -> Dict[str, str]:
        """Получение соответствия атрибутов метрикам для платного трафика"""
        return PAID_ATTRIBUTES_MAPPING.copy()

    def get_metric_names(self) -> Dict[str, str]:
        """Получение русских названий метрик для платного трафика"""
        return PAID_METRIC_NAMES.copy()

    def get_traffic_type(self) -> Literal["paid", "free"]:
        """Тип трафика - платный"""
        return "paid"

    def get_main_dimensions(self) -> List[str]:
        """Получение основных измерений - типы платформ DirectPlatformType"""
        return ["ym:ad:CROSS_DEVICE_LAST_SIGNIFICANTDirectPlatformType"]

    def get_detail_dimensions(self) -> List[str]:
        """Для платного трафика детализация не нужна"""
        return []

    def _get_main_header_name(self) -> str:
        """Название для первого столбца"""
        return "Тип платформы"

    def _get_main_filters(self) -> Optional[str]:
        """Фильтры для основного уровня - нет фильтров"""
        return None

    def _build_detail_filter(self, main_id: str) -> Optional[str]:
        """Для платного трафика детализация не нужна"""
        return None

    async def generate_report(self, report: Report) -> Optional[ReportData]:
        """Генерация отчета для платного трафика"""
        await self._log_generation_start(report)

        try:
            # Получаем клиентов Директа
            clients_data = await self.metrika_client.get_clients(
                self.yandex_metrika_integration
            )
            if not clients_data or "clients" not in clients_data:
                logger.warning("🔹 No Direct clients found")
                await self._log_generation_complete(report, False)
                return None

            clients = clients_data["clients"]
            client_logins = [
                str(client["chief_login"])
                for client in clients
                if "chief_login" in client
            ]

            if not client_logins:
                logger.warning("🔹 No Direct client logins found")
                await self._log_generation_complete(report, False)
                return None

            logger.info(f"🔹 Found {len(client_logins)} Direct clients")

            # Получаем метрики и названия целей
            goal_metrics, goal_names = await self._get_goal_metrics_and_names(report)
            logger.info(f"🔹 Found {len(goal_metrics)} goal metrics")

            # Формируем список выбранных метрик
            selected_metrics = self._build_selected_metrics(report, goal_metrics)
            logger.info(f"🔹 Total metrics to fetch: {len(selected_metrics)}")

            # Получаем данные по типам платформ
            headers = self._build_main_headers(selected_metrics, goal_names, report)
            rows = []

            platform_types_data = await self.metrika_client.get_metrika_data(
                dimensions=self.get_main_dimensions(),
                metrics=selected_metrics,
                date_1=report.date_1,
                date_2=report.date_2,
                yandexMetrikaIntegration=self.yandex_metrika_integration,
                direct_client_logins=",".join(client_logins),
            )

            if not platform_types_data or not platform_types_data.data:
                logger.error("🔹 No data received from Yandex Metrika for paid traffic")
                await self._log_generation_complete(report, False)
                return None

            # Предварительная карта индексов метрик
            metric_index = {name: idx for idx, name in enumerate(selected_metrics)}

            # Обрабатываем данные по типам платформ
            total_row = None
            for platform_type in platform_types_data.data:
                platform_type_name = platform_type["dimensions"][0]["name"]

                # Строим строку данных
                row = self._build_data_row(
                    platform_type_name,
                    platform_type,
                    selected_metrics,
                    report,
                    metric_index,
                )
                rows.append(row)

                # Суммируем данные для итоговой строки "Яндекс.Директ"
                if total_row is None:
                    total_row = [0] * len(row)
                    total_row[0] = "  Яндекс.Директ"  # Первая колонка - название

                # Суммируем численные значения
                for i in range(1, len(row)):
                    if isinstance(row[i], (int, float)):
                        total_row[i] += row[i]

            # Если есть данные, заменяем их на одну суммарную строку
            if total_row:
                # Пересчитываем расчетные метрики для суммарной строки
                if report.selected_metrics and len(total_row) > 1:
                    # Извлекаем базовые данные из суммарной строки
                    base_data = self._extract_base_data_from_row(
                        total_row, selected_metrics, report
                    )

                    # Вычисляем расчетные метрики
                    calculated_values = self._calculate_metrics_from_base_data(
                        base_data, report
                    )

                    # Заменяем расчетные метрики в суммарной строке
                    if calculated_values:
                        # Находим позицию начала расчетных метрик
                        base_metrics_count = len(selected_metrics) + len(
                            report.selected_attributes
                        )
                        start_idx = 1 + base_metrics_count  # +1 для названия столбца

                        for i, value in enumerate(calculated_values):
                            if start_idx + i < len(total_row):
                                total_row[start_idx + i] = round(value, 2)

                rows = [total_row]

            logger.info(
                f"🔹 Generated report with {len(headers)} columns and {len(rows)} rows"
            )

            result = ReportData(headers=headers, rows=rows, meta_data=[])

            await self._log_generation_complete(report, True)
            return result

        except Exception as e:
            logger.error(f"🔹 Error generating paid report: {str(e)}")
            await self._log_generation_complete(report, False)
            return None

    def _extract_base_data_from_row(
        self, row: List, selected_metrics: List[str], report: Report
    ) -> Dict[str, float]:
        """Извлечение базовых данных из строки для пересчета метрик"""
        base_data = {"cost": 0, "clicks": 0, "visits": 0, "revenue": 0, "goal": 0}

        # Пропускаем первый столбец (название)
        col_idx = 1

        # Пропускаем атрибуты
        col_idx += len(report.selected_attributes)

        # Извлекаем базовые метрики
        for metric in selected_metrics:
            if col_idx < len(row) and isinstance(row[col_idx], (int, float)):
                value = row[col_idx]

                if "cost" in metric.lower() or "RUBConvertedAdCost" in metric:
                    base_data["cost"] += value
                elif "clicks" in metric.lower():
                    base_data["clicks"] += value
                elif "visits" in metric.lower() and "goal" not in metric.lower():
                    base_data["visits"] += value
                elif (
                    "revenue" in metric.lower()
                    or "ecommerceRUBConvertedRevenue" in metric
                ):
                    base_data["revenue"] += value
                elif "goal" in metric.lower() and "visits" in metric.lower():
                    base_data["goal"] += value

            col_idx += 1

        return base_data

    def _calculate_metrics_from_base_data(
        self, base_data: Dict[str, float], report: Report
    ) -> List[float]:
        """Вычисление расчетных метрик из базовых данных"""
        if not report.selected_metrics:
            return []

        calculated = []

        # Получаем достижения целей для CPA/CPO
        goal_achieved = base_data["goal"]

        # Если есть специфичные цели для CPA/CPO, используем их
        if ("cpa" in report.selected_metrics and report.cpa_goal) or (
            "cpo" in report.selected_metrics and report.cpo_goal
        ):
            # В данном случае goal_achieved уже содержит суммарное значение всех целей
            # Для более точного расчета нужно было бы отдельно запрашивать каждую цель
            pass

        # Вычисляем метрики с помощью утилиты
        from app.core.utils import calculate_metrics

        metrics_result = calculate_metrics(
            cost=base_data["cost"],
            clicks=int(base_data["clicks"]),
            visits=int(base_data["visits"]),
            goal_achieved=int(goal_achieved),
            revenue=base_data["revenue"],
            selected_metrics=report.selected_metrics,
        )

        # Формируем список значений в том же порядке что и в selected_metrics
        for metric in report.selected_metrics:
            value = getattr(metrics_result, metric, 0)
            calculated.append(value or 0)

        return calculated
