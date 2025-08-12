from __future__ import annotations

import asyncio
from typing import List, Dict, Optional, Tuple

from app.database.models.report import Report
from app.schemas.report import ReportData
from app.schemas.integration import YandexMetrikaIntegration, GoogleAnalyticsIntegration
from app.services.providers.registry import ProviderRegistry

SourceSpec = Dict[str, str]  # {"provider": str, "traffic_kind": str}


async def collect_reports(
    report: Report,
    sources: List[SourceSpec],
    registry: ProviderRegistry,
    yandex_integration: Optional[YandexMetrikaIntegration] = None,
    google_integration: Optional[GoogleAnalyticsIntegration] = None,
    concurrency: int = 5,
) -> List[Tuple[str, ReportData]]:
    """Собирает данные отчетов из разных провайдеров параллельно.

    Возвращает список кортежей (provider_slug, ReportData).
    """
    if not sources:
        return []

    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(spec: SourceSpec) -> Optional[Tuple[str, ReportData]]:
        provider_slug = spec.get("provider", "yandex_metrika")
        traffic_kind = spec.get("traffic_kind", "all")

        # Временно меняем вид трафика в исходном Report
        previous_source = report.source
        report.source = traffic_kind
        try:
            if provider_slug == "yandex_metrika":
                if not yandex_integration:
                    return None
                provider = registry.get_yandex(yandex_integration)
            elif provider_slug == "google_analytics":
                provider = registry.get_google(google_integration)
            else:
                return None

            async with semaphore:
                data = await provider.generate_report(report)

            if not data:
                return None
            return provider_slug, data
        finally:
            # Восстанавливаем исходный source
            report.source = previous_source

    tasks = [run_one(spec) for spec in sources]
    results = await asyncio.gather(*tasks)

    return [(slug, data) for item in results if item for slug, data in [item]]
