from typing import List, Dict, Optional, Literal
from loguru import logger

from app.database.models.report import Report
from app.schemas.report import ReportData
from app.core.constants import (
    PAID_METRICS,
    PAID_ATTRIBUTES_MAPPING,
    DIRECT_METRIC_NAMES,
)
from .base import BaseReportGenerator


class DirectReportGenerator(BaseReportGenerator):
    """Генератор отчетов для Яндекс.Директ"""

    def __init__(
        self,
        metrika_client,
        yandex_metrika_integration,
        attribution: str = "CROSS_DEVICE_LAST_SIGNIFICANT",
    ):
        super().__init__(metrika_client, yandex_metrika_integration)
        self.attribution = attribution

    def get_base_metrics(self) -> List[str]:
        """Получение базовых метрик для Direct"""
        return PAID_METRICS.copy()

    def get_attributes_mapping(self) -> Dict[str, str]:
        """Получение соответствия атрибутов метрикам для Direct"""
        return PAID_ATTRIBUTES_MAPPING.copy()

    def get_metric_names(self) -> Dict[str, str]:
        """Получение русских названий метрик для Direct"""
        return DIRECT_METRIC_NAMES.copy()

    def get_traffic_type(self) -> Literal["paid", "free"]:
        """Тип трафика - платный (Директ)"""
        return "paid"

    def get_main_dimensions(self) -> List[str]:
        """Получение основных измерений - рекламные кампании (заказы)"""
        return [f"ym:ad:{self.attribution}DirectOrder"]

    def get_detail_dimensions(self) -> List[str]:
        """Получение детальных измерений - группы объявлений"""
        return [f"ym:ad:{self.attribution}DirectBannerGroup"]

    def _get_main_header_name(self) -> str:
        """Название для первого столбца"""
        return "Рекламная кампания/Группа объявлений"

    def _get_main_filters(self) -> Optional[str]:
        """Фильтры для основного уровня - нет фильтров"""
        return None

    def _build_detail_filter(self, main_id: str) -> Optional[str]:
        """Построение фильтра для групп объявлений в рамках кампании"""
        return f"ym:ad:{self.attribution}DirectOrder=='{main_id}'"

    async def generate_report(self, report: Report) -> Optional[ReportData]:
        """Генерация Direct отчета"""
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

            # Получаем данные по рекламным кампаниям (заказам)
            headers = self._build_main_headers(selected_metrics, goal_names, report)
            rows = []

            orders_data = await self.metrika_client.get_metrika_data(
                dimensions=self.get_main_dimensions(),
                metrics=selected_metrics,
                yandexMetrikaIntegration=self.yandex_metrika_integration,
                date_1=report.date_1,
                date_2=report.date_2,
                direct_client_logins=",".join(client_logins),
            )

            if not orders_data or not orders_data.data:
                logger.error(
                    "🔹 No data received from Yandex Metrika for Direct orders"
                )
                await self._log_generation_complete(report, False)
                return None

            # Предварительная карта индексов метрик
            metric_index = {name: idx for idx, name in enumerate(selected_metrics)}

            # Обрабатываем каждую рекламную кампанию
            for order in orders_data.data:
                order_name = order["dimensions"][0]["name"]
                order_id = order["dimensions"][0]["id"]

                # Добавляем строку кампании
                order_row = self._build_data_row(
                    order_name,
                    order,
                    selected_metrics,
                    report,
                    metric_index,
                    is_main=True,
                )
                # Применяем форматирование к данным кампании (временно простое)
                formatted_order_row = self._format_row_values_simple(order_row)
                rows.append(formatted_order_row)

                # Получаем данные по группам объявлений для этой кампании
                groups_data = await self.metrika_client.get_metrika_data(
                    dimensions=self.get_detail_dimensions(),
                    metrics=selected_metrics,
                    date_1=report.date_1,
                    yandexMetrikaIntegration=self.yandex_metrika_integration,
                    date_2=report.date_2,
                    filters=self._build_detail_filter(order_id),
                    direct_client_logins=",".join(client_logins),
                )

                if groups_data and groups_data.data:
                    for group in groups_data.data:
                        group_name = group["dimensions"][0]["name"]

                        # Добавляем строку группы с отступом
                        group_row = self._build_data_row(
                            f"  {group_name}",
                            group,
                            selected_metrics,
                            report,
                            metric_index,
                            is_main=False,
                        )
                        # Применяем форматирование (временно простое)
                        formatted_group_row = self._format_row_values_simple(group_row)
                        rows.append(formatted_group_row)
                else:
                    logger.warning(f"🔹 No groups data for order {order_name}")

            logger.info(
                f"🔹 Generated Direct report with {len(headers)} columns and {len(rows)} rows"
            )

            result = ReportData(headers=headers, rows=rows, meta_data=[])

            await self._log_generation_complete(report, True)
            return result

        except Exception as e:
            logger.error(f"🔹 Error generating Direct report: {str(e)}")
            await self._log_generation_complete(report, False)
            return None

    def _format_row_values_simple(self, row: List) -> List:
        """Временное форматирование значений: округление чисел, формат времени не применяется.
        До ввода схемы колонок.
        """
        formatted_row: List = []
        for i, value in enumerate(row):
            if i == 0:
                formatted_row.append(value)
                continue
            if isinstance(value, float):
                formatted_row.append(round(value, 2))
            else:
                formatted_row.append(value)
        return formatted_row
