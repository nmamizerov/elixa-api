from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Literal
from loguru import logger
import asyncio

from app.database.models.report import Report
from app.schemas.report import ReportData
from app.adapters.y_metrika.client import YandexMetrikaClient
from app.core.utils import calculate_metrics
from app.core.constants import BASE_ADDITIONAL_METRICS
from app.schemas.integration import YandexMetrikaIntegration
from .selectors import build_selected_metrics, dedup_keep_order


class BaseReportGenerator(ABC):
    """Базовый класс для генераторов отчетов.

    Контракт:
    - Наследники обязаны предоставить базовые метрики, маппинг атрибутов,
      русские названия, тип трафика и измерения (основные/детальные).
    - Метод generate_report формирует ReportData (headers/rows/meta_data).
    """

    def __init__(
        self,
        metrika_client: YandexMetrikaClient,
        yandex_metrika_integration: YandexMetrikaIntegration,
    ):
        self.metrika_client = metrika_client
        self.yandex_metrika_integration = yandex_metrika_integration

    @abstractmethod
    async def generate_report(self, report: Report) -> Optional[ReportData]:
        """Генерация отчета"""
        pass

    @abstractmethod
    def get_base_metrics(self) -> List[str]:
        """Получение базовых метрик для типа отчета"""
        pass

    @abstractmethod
    def get_attributes_mapping(self) -> Dict[str, str]:
        """Получение соответствия атрибутов метрикам"""
        pass

    @abstractmethod
    def get_metric_names(self) -> Dict[str, str]:
        """Получение русских названий метрик"""
        pass

    @abstractmethod
    def get_traffic_type(self) -> Literal["paid", "free"]:
        """Получение типа трафика для работы с целями"""
        pass

    @abstractmethod
    def get_main_dimensions(self) -> List[str]:
        """Получение основных измерений для группировки"""
        pass

    @abstractmethod
    def get_detail_dimensions(self) -> List[str]:
        """Получение детальных измерений для подгруппировки"""
        pass

    async def _get_goal_metrics_and_names(
        self, report: Report
    ) -> Tuple[List[str], Dict[str, str]]:
        """Получение метрик и названий целей"""
        return await self.metrika_client.get_goal_metrics(
            report.goals, self.get_traffic_type()
        )

    def _build_selected_metrics(
        self, report: Report, goal_metrics: List[str]
    ) -> List[str]:
        """Формирование списка метрик для запроса к Яндекс.Метрике (стабильный порядок).

        Порядок: базовые → цели → атрибуты. Дубликаты удаляются без изменения порядка.
        """
        selected_metrics = build_selected_metrics(
            base_metrics=self.get_base_metrics(),
            goal_metrics=goal_metrics,
            selected_attributes=report.selected_attributes,
            attributes_mapping=self.get_attributes_mapping(),
        )
        return selected_metrics

    def _build_main_headers(
        self, selected_metrics: List[str], goal_names: Dict[str, str], report: Report
    ) -> List[str]:
        """Формирование заголовков для основного уровня группировки"""
        # Первый столбец - название группы (источник/платформа/кампания)
        headers = [self._get_main_header_name()]
        metric_names = self.get_metric_names()

        # Добавляем заголовки для атрибутов
        for attr in report.selected_attributes:
            attr_mapping = self.get_attributes_mapping()
            if attr in attr_mapping:
                metric_key = attr_mapping[attr]
                if metric_key in metric_names:
                    headers.append(metric_names[metric_key])
                else:
                    headers.append(attr.title())

        # Добавляем заголовки для базовых и целевых метрик
        for metric in selected_metrics:
            if metric in goal_names:
                headers.append(goal_names[metric])
            elif metric in metric_names:
                headers.append(metric_names[metric])
            else:
                # Пропускаем метрики атрибутов, которые уже добавлены выше
                attr_mapping = self.get_attributes_mapping()
                if metric not in attr_mapping.values():
                    headers.append(metric)

        # Добавляем заголовки для выбранных пользователем метрик (cac, cpo, cpa, etc.)
        if report.selected_metrics:
            for metric in report.selected_metrics:
                if metric in metric_names:
                    headers.append(metric_names[metric])
                else:
                    headers.append(metric.upper())

        # Добавляем заголовки для дополнительных метрик (если есть)
        additional_metrics = (
            report.additional_metrics.split(",") if report.additional_metrics else []
        )
        for metric in additional_metrics:
            metric = metric.strip()
            if metric in BASE_ADDITIONAL_METRICS and metric not in (
                report.selected_metrics or []
            ):
                if metric in metric_names:
                    headers.append(metric_names[metric])
                else:
                    headers.append(metric.upper())

        return headers

    @abstractmethod
    def _get_main_header_name(self) -> str:
        """Получение названия для первого столбца"""
        pass

    async def _process_hierarchical_data(
        self, report: Report, selected_metrics: List[str], goal_names: Dict[str, str]
    ) -> Tuple[List[str], List[List]]:
        """Обработка иерархических данных с основным и детальным уровнями.

        Важно: детальные запросы выполняются с ограниченной параллельностью,
        чтобы не превышать лимиты API.
        """
        headers = self._build_main_headers(selected_metrics, goal_names, report)
        rows: List[List] = []

        # Получаем данные основного уровня
        main_data = await self.metrika_client.get_metrika_data(
            dimensions=self.get_main_dimensions(),
            metrics=selected_metrics,
            date_1=report.date_1,
            date_2=report.date_2,
            yandexMetrikaIntegration=self.yandex_metrika_integration,
            filters=self._get_main_filters(),
        )

        if not main_data or not main_data.data:
            return headers, rows

        # Предварительная карта индексов для метрик
        metric_index = {name: idx for idx, name in enumerate(selected_metrics)}

        # Подготовка задач на детали с ограничением параллельности
        semaphore = asyncio.Semaphore(5)
        detail_dims = self.get_detail_dimensions()

        async def fetch_details(main_id: str):
            if not detail_dims:
                return None
            async with semaphore:
                return await self.metrika_client.get_metrika_data(
                    dimensions=detail_dims,
                    metrics=selected_metrics,
                    date_1=report.date_1,
                    yandexMetrikaIntegration=self.yandex_metrika_integration,
                    date_2=report.date_2,
                    filters=self._build_detail_filter(main_id),
                )

        detail_tasks = []

        # Обрабатываем каждый элемент основного уровня
        for main_item in main_data.data:
            main_name = main_item["dimensions"][0]["name"]
            main_id = main_item["dimensions"][0]["id"]

            # Добавляем строку основного уровня
            main_row = self._build_data_row(
                main_name,
                main_item,
                selected_metrics,
                report,
                metric_index,
                is_main=True,
            )
            rows.append(main_row)

            # Планируем детальные данные
            detail_tasks.append(fetch_details(main_id))

        # Получаем детали (если есть)
        details_results = await asyncio.gather(*detail_tasks) if detail_dims else []

        # Присоединяем детальные строки
        for detail_data in details_results:
            if detail_data and detail_data.data:
                for detail_item in detail_data.data:
                    detail_name = detail_item["dimensions"][0]["name"]
                    detail_row = self._build_data_row(
                        f"  {detail_name}",
                        detail_item,
                        selected_metrics,
                        report,
                        metric_index,
                        is_main=False,
                    )
                    rows.append(detail_row)

        return headers, rows

    def _build_data_row(
        self,
        name: str,
        item: Dict,
        selected_metrics: List[str],
        report: Report,
        metric_index: Dict[str, int],
        is_main: bool = True,
    ) -> List:
        """Построение строки данных.

        Использует карту индексов метрик для стабильного и быстрого доступа.
        """
        row = [name]

        metrics_data = item.get("metrics", [])

        # Добавляем значения атрибутов сначала
        for attr in report.selected_attributes:
            attr_mapping = self.get_attributes_mapping()
            if attr in attr_mapping:
                metric_key = attr_mapping[attr]
                idx = metric_index.get(metric_key)
                if idx is not None and idx < len(metrics_data):
                    row.append(metrics_data[idx])
                else:
                    row.append(0)

        # Добавляем основные метрики (исключая атрибутные)
        attr_values = set(self.get_attributes_mapping().values())
        for metric in selected_metrics:
            if metric in attr_values:
                continue
            idx = metric_index.get(metric)
            value = (
                metrics_data[idx] if idx is not None and idx < len(metrics_data) else 0
            )
            row.append(value)

        # Вычисляем выбранные пользователем метрики (cac, cpo, cpa, etc.)
        if report.selected_metrics and len(metrics_data) > 0:
            calculated_values = self._calculate_user_selected_metrics(
                metrics_data, selected_metrics, report
            )
            row.extend(calculated_values)

        # Вычисляем дополнительные метрики (если есть и не пересекаются с выбранными)
        additional_metrics = (
            report.additional_metrics.split(",") if report.additional_metrics else []
        )
        additional_metrics = [m.strip() for m in additional_metrics if m.strip()]
        additional_metrics = [
            m for m in additional_metrics if m not in (report.selected_metrics or [])
        ]

        if additional_metrics and len(metrics_data) > 0:
            calculated = self._calculate_additional_metrics(
                metrics_data, selected_metrics, additional_metrics
            )
            row.extend(calculated)

        return row

    def _extract_base_data(
        self, metrics_data: List, selected_metrics: List[str], report: Report
    ) -> Dict[str, float]:
        """Извлечение базовых данных для расчетов (эвристика до перехода на column schema)."""
        return {
            "cost": self._get_metric_value(metrics_data, selected_metrics, "cost"),
            "clicks": self._get_metric_value(metrics_data, selected_metrics, "clicks"),
            "visits": self._get_metric_value(metrics_data, selected_metrics, "visits"),
            "revenue": self._get_metric_value(
                metrics_data, selected_metrics, "revenue"
            ),
            "goal": self._get_metric_value(metrics_data, selected_metrics, "goal"),
        }

    @abstractmethod
    def _get_main_filters(self) -> Optional[str]:
        """Получение фильтров для основного уровня"""
        pass

    @abstractmethod
    def _build_detail_filter(self, main_id: str) -> Optional[str]:
        """Построение фильтра для детального уровня на основе ID основного элемента"""
        pass

    def _calculate_user_selected_metrics(
        self,
        metrics_data: List,
        selected_metrics: List[str],
        report: Report,
    ) -> List:
        """Вычисление выбранных пользователем метрик (cac, cpo, cpa, etc.)"""
        calculated = []

        if not report.selected_metrics:
            return calculated

        # Извлекаем базовые значения для расчетов
        cost = self._get_metric_value(metrics_data, selected_metrics, "cost")
        clicks = self._get_metric_value(metrics_data, selected_metrics, "clicks")
        visits = self._get_metric_value(metrics_data, selected_metrics, "visits")
        revenue = self._get_metric_value(metrics_data, selected_metrics, "revenue")

        # Получаем достижения целей для CPA/CPO
        goal_achieved = 0

        # Если есть CPA цель, используем её для расчета CPA
        if "cpa" in report.selected_metrics and report.cpa_goal:
            cpa_goal_metric = f"ym:s:goal{report.cpa_goal}visits"
            if self.get_traffic_type() == "paid":
                cpa_goal_metric = f"ym:ad:goal{report.cpa_goal}visits"
            if cpa_goal_metric in selected_metrics:
                idx = selected_metrics.index(cpa_goal_metric)
                if idx < len(metrics_data):
                    goal_achieved = float(metrics_data[idx] or 0)

        # Если есть CPO цель, используем её для расчета CPO
        if "cpo" in report.selected_metrics and report.cpo_goal:
            cpo_goal_metric = f"ym:s:goal{report.cpo_goal}visits"
            if self.get_traffic_type() == "paid":
                cpo_goal_metric = f"ym:ad:goal{report.cpo_goal}visits"
            if cpo_goal_metric in selected_metrics:
                idx = selected_metrics.index(cpo_goal_metric)
                if idx < len(metrics_data):
                    goal_achieved = max(goal_achieved, float(metrics_data[idx] or 0))

        # Если CPA/CPO целей нет, используем общие цели
        if goal_achieved == 0:
            goal_achieved = self._get_metric_value(
                metrics_data, selected_metrics, "goal"
            )

        # Вычисляем метрики с помощью утилиты
        metrics_result = calculate_metrics(
            cost=cost,
            clicks=int(clicks),
            visits=int(visits),
            goal_achieved=int(goal_achieved),
            revenue=revenue,
            selected_metrics=report.selected_metrics,
        )

        # Формируем список значений в том же порядке что и в selected_metrics
        for metric in report.selected_metrics:
            value = getattr(metrics_result, metric, 0)
            calculated.append(value or 0)

        return calculated

    def _calculate_additional_metrics(
        self,
        metrics_data: List,
        selected_metrics: List[str],
        additional_metrics: List[str],
    ) -> List:
        """Расчет дополнительных метрик"""
        calculated = []

        # Извлекаем базовые значения для расчетов
        cost = self._get_metric_value(metrics_data, selected_metrics, "cost")
        clicks = self._get_metric_value(metrics_data, selected_metrics, "clicks")
        visits = self._get_metric_value(metrics_data, selected_metrics, "visits")
        revenue = self._get_metric_value(metrics_data, selected_metrics, "revenue")
        goal_achieved = self._get_metric_value(metrics_data, selected_metrics, "goal")

        # Расчитываем метрики с помощью утилиты
        metrics_result = calculate_metrics(
            cost=cost,
            clicks=int(clicks),
            visits=int(visits),
            goal_achieved=int(goal_achieved),
            revenue=revenue,
            selected_metrics=additional_metrics,
        )

        # Формируем список значений в том же порядке
        for metric in additional_metrics:
            value = getattr(metrics_result, metric, 0)
            calculated.append(value or 0)

        return calculated

    def _get_metric_value(
        self, metrics_data: List, selected_metrics: List[str], metric_type: str
    ) -> float:
        """Извлечение значения метрики по типу (временная эвристика).

        TODO: перейти на column schema, чтобы не полагаться на подстроки в именах.
        """
        value = 0

        for i, metric_name in enumerate(selected_metrics):
            if i < len(metrics_data):
                if metric_type == "cost" and (
                    "cost" in metric_name.lower() or "RUBConvertedAdCost" in metric_name
                ):
                    value += float(metrics_data[i] or 0)
                elif metric_type == "clicks" and "clicks" in metric_name.lower():
                    value += float(metrics_data[i] or 0)
                elif metric_type == "visits" and "visits" in metric_name.lower():
                    value += float(metrics_data[i] or 0)
                elif metric_type == "revenue" and (
                    "revenue" in metric_name.lower()
                    or "ecommerceRUBConvertedRevenue" in metric_name
                ):
                    value += float(metrics_data[i] or 0)
                elif (
                    metric_type == "goal"
                    and "goal" in metric_name.lower()
                    and "visits" in metric_name.lower()
                ):
                    value += float(metrics_data[i] or 0)

        return value

    async def _log_generation_start(self, report: Report):
        """Логирование начала генерации отчета"""
        logger.info(
            f"🔹 Starting {self.__class__.__name__} generation for report {report.id}"
        )
        logger.info(
            f"🔹 Company: {report.company.name if report.company else 'Unknown'}"
        )
        logger.info(f"🔹 Period: {report.date_1} - {report.date_2}")
        logger.info(f"🔹 Goals: {len(report.goals)}")

    async def _log_generation_complete(self, report: Report, success: bool):
        """Логирование завершения генерации отчета"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(
            f"🔹 {self.__class__.__name__} generation {status} for report {report.id}"
        )
