import asyncio
import csv
import os
import time
from typing import Any, Dict, List, Optional, Union
from loguru import logger

from app.schemas.report import CalculatedMetrics, ReportData


def calculate_cpc(cost: float, clicks: int) -> float:
    """Расчет стоимости клика (CPC)"""
    if clicks == 0:
        return 0.0
    return round(cost / clicks, 2)


def calculate_cpa(cost: float, conversions: int) -> float:
    """Расчет стоимости конверсии (CPA)"""
    if conversions == 0:
        return 0.0
    return round(cost / conversions, 2)


def calculate_cpo(cost: float, orders: int) -> float:
    """Расчет стоимости заказа (CPO)"""
    if orders == 0:
        return 0.0
    return round(cost / orders, 2)


def calculate_cr(conversions: int, visits: int) -> float:
    """Расчет коэффициента конверсии (CR)"""
    if visits == 0:
        return 0.0
    return round((conversions / visits) * 100, 2)


def calculate_romi(revenue: float, cost: float) -> float:
    """Расчет возврата на инвестиции в маркетинг (ROMI)"""
    if cost == 0:
        return 0.0
    return round(((revenue - cost) / cost) * 100, 2)


def calculate_roi(revenue: float, cost: float) -> float:
    """Расчет возврата на инвестиции (ROI)"""
    if cost == 0:
        return 0.0
    return round((revenue / cost) * 100, 2)


def calculate_drr(cost: float, revenue: float) -> float:
    """Расчет доли рекламных расходов (ДРР)"""
    if revenue == 0:
        return 0.0
    return round((cost / revenue) * 100, 2)


def calculate_cac(cost: float, new_customers: int) -> float:
    """Расчет стоимости привлечения клиента (CAC)"""
    if new_customers == 0:
        return 0.0
    return round(cost / new_customers, 2)


def calculate_metrics(
    cost: float,
    clicks: int,
    visits: int,
    goal_achieved: int,
    revenue: float,
    selected_metrics: List[str],
    new_customers: Optional[int] = None,
) -> CalculatedMetrics:
    """Расчет всех метрик на основе исходных данных"""
    metrics = CalculatedMetrics()

    if "cpc" in selected_metrics and clicks > 0:
        metrics.cpc = calculate_cpc(cost, clicks)

    if "cr" in selected_metrics and visits > 0:
        metrics.cr = calculate_cr(goal_achieved, visits)

    if "romi" in selected_metrics and cost > 0:
        metrics.romi = calculate_romi(revenue, cost)

    if "roi" in selected_metrics and cost > 0:
        metrics.roi = calculate_roi(revenue, cost)

    if "drr" in selected_metrics and revenue > 0:
        metrics.drr = calculate_drr(cost, revenue)

    if "cac" in selected_metrics and new_customers is not None:
        metrics.cac = calculate_cac(cost, new_customers)

    if "cpa" in selected_metrics and goal_achieved > 0:
        metrics.cpa = calculate_cpa(cost, goal_achieved)

    if "cpo" in selected_metrics and goal_achieved > 0:
        metrics.cpo = calculate_cpo(cost, goal_achieved)

    return metrics


def format_value(value: Union[int, float], metric_name: str) -> str:
    """Форматирует значение в соответствии с типом метрики"""
    if not isinstance(value, (int, float)):
        return str(value)

    # Процентные метрики
    if any(
        suffix in metric_name.lower()
        for suffix in ["%", "rate", "cr", "romi", "roi", "drr"]
    ):
        return f"{value:.2f}%"

    # Денежные метрики
    if any(
        prefix in metric_name.lower()
        for prefix in ["rub", "cost", "cpc", "cpa", "cpo", "cac"]
    ):
        return f"{value:,.2f} ₽"

    # Временные метрики (секунды)
    if "duration" in metric_name.lower() or "time" in metric_name.lower():
        minutes = int(value // 60)
        seconds = int(value % 60)
        return f"{minutes}:{seconds:02d}"

    # Обычные числовые метрики
    if isinstance(value, float):
        return f"{value:.2f}"

    return str(value)


async def save_report_to_excel(
    report_data: ReportData, file_prefix: str = "yandex_report"
) -> str:
    """Сохранение данных отчета в Excel формате в S3"""
    from app.services.s3_service import s3_service

    file_name = await s3_service.upload_report_excel(report_data, file_prefix)
    if not file_name:
        raise Exception("Failed to upload Excel report to S3")

    return file_name


# Alias для обратной совместимости
async def save_report_to_csv(
    report_data: ReportData, file_prefix: str = "yandex_report"
) -> str:
    """Deprecated: используйте save_report_to_excel"""
    logger.warning("save_report_to_csv is deprecated, use save_report_to_excel instead")
    return await save_report_to_excel(report_data, file_prefix)


def add_metadata_to_report(report_data: ReportData, metadata: List[Any]) -> ReportData:
    """Добавляет метаданные в отчет"""
    if not report_data:
        return report_data

    # Создаем строки метаданных
    metadata_rows = []
    for meta_item in metadata:
        if isinstance(meta_item, list):
            metadata_rows.append(meta_item)
        else:
            metadata_rows.append([str(meta_item)])

    # Добавляем пустую строку-разделитель
    metadata_rows.append([""])

    # Создаем новый объект с метаданными
    result_data = ReportData(
        headers=report_data.headers, rows=report_data.rows, meta_data=metadata_rows
    )

    return result_data


def get_safe_value(data: Dict[str, Any], key: str, default: Any = 0) -> Any:
    """Безопасное получение значения из словаря с обработкой ошибок"""
    try:
        value = data.get(key, default)
        if value is None:
            return default
        return value
    except (KeyError, TypeError):
        return default


def merge_metric_batches(
    base_result: Dict[str, Any], batch_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Объединяет результаты нескольких запросов к API в один результат"""
    if not batch_results:
        return base_result

    # Проверяем соответствие размерностей данных
    for batch_result in batch_results:
        if not batch_result or "data" not in batch_result:
            continue

        if len(base_result["data"]) != len(batch_result["data"]):
            continue

        # Объединяем метрики для каждого измерения
        for j, item in enumerate(base_result["data"]):
            if j < len(batch_result["data"]):
                item["metrics"].extend(batch_result["data"][j]["metrics"])

    return base_result
