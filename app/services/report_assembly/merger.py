from __future__ import annotations

from typing import List, Tuple

from app.schemas.report import ReportData


def union_merge(results: List[Tuple[str, ReportData]]) -> ReportData:
    """Объединяет результаты провайдеров в единый ReportData (union по строкам).

    Добавляет первую колонку "Провайдер". Не пытается выравнивать разный набор
    заголовков — использует заголовки первого результата как базовые.
    """
    if not results:
        return ReportData(headers=[], rows=[], meta_data=["Empty union"])

    provider0, first = results[0]
    headers = ["Провайдер"] + list(first.headers)
    rows: List[List] = []

    for provider, data in results:
        # Если заголовки отличаются — просто добавим строки как есть
        for row in data.rows:
            rows.append([provider] + list(row))

    meta = ["Union of providers", f"Providers: {[p for p,_ in results]}"]
    return ReportData(headers=headers, rows=rows, meta_data=meta)
