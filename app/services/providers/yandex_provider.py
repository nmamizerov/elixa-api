from __future__ import annotations

from typing import Optional

from app.adapters.y_metrika.client import YandexMetrikaClient
from app.schemas.integration import YandexMetrikaIntegration
from app.database.models.report import Report
from app.schemas.report import ReportData
from app.services.yandex_report_generators import ReportGeneratorFactory
from .base import AnalyticsProvider


class YandexMetrikaProvider(AnalyticsProvider):
    slug = "yandex_metrika"

    def __init__(self, integration: YandexMetrikaIntegration):
        self.client = YandexMetrikaClient()
        self.factory = ReportGeneratorFactory(self.client, integration)

    async def generate_report(self, report: Report) -> Optional[ReportData]:
        # Особый случай: "all" => создаем новый free-генератор и включаем рекламный трафик
        if report.source == "all":
            from app.services.yandex_report_generators.free_report_generator import (
                FreeReportGenerator,
            )

            generator = self.factory.create_generator("free")
            if isinstance(generator, FreeReportGenerator):
                generator.include_ad = True
            return await generator.generate_report(report)

        # Обычные случаи
        generator = self.factory.get_generator(report.source)
        return await generator.generate_report(report)
