from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List, Literal

from app.database.models.report import Report
from app.schemas.report import ReportData


ProviderSlug = Literal["yandex_metrika", "google_analytics"]
TrafficKind = Literal["paid", "free", "all", "direct"]


class AnalyticsProvider(ABC):
    """Базовый интерфейс провайдера аналитики."""

    slug: ProviderSlug

    @abstractmethod
    async def generate_report(self, report: Report) -> Optional[ReportData]:
        """Сгенерировать отчет согласно параметрам в модели Report."""
        raise NotImplementedError


class MultiSourceProvider(AnalyticsProvider):
    """Интерфейс для провайдера, поддерживающего несколько источников в одном отчете."""

    @abstractmethod
    async def generate_multi_source_report(
        self, report: Report, sources: List[TrafficKind]
    ) -> Optional[ReportData]:
        raise NotImplementedError
