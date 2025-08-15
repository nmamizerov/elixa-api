from __future__ import annotations

from typing import Optional, Any
import json
import os

from app.database.models.report import Report
from app.schemas.report import ReportData
from .base import AnalyticsProvider


from google.analytics.data_v1beta import (  # type: ignore
    BetaAnalyticsDataClient as GAClient,  # type: ignore
)
from google.analytics.data_v1beta.types import (  # type: ignore
    RunReportRequest,  # type: ignore
    DateRange,  # type: ignore
    Dimension,  # type: ignore
    Metric,  # type: ignore
)


from google.oauth2 import service_account
from app.core.config import settings
from app.database.repositories.integration_repository import IntegrationRepository
from app.database.config import SessionLocal
from app.schemas.integration import GoogleAnalyticsIntegration

GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

_GA_VERSION = "v1beta"


class GoogleAnalyticsProvider(AnalyticsProvider):
    slug = "google_analytics"

    def __init__(self, integration: Optional[GoogleAnalyticsIntegration] = None):
        self._client: Any | None = None
        self._integration = integration

    def _get_client(self) -> Any:
        if self._client:
            return self._client
        credentials = None

        # Используем файл ga_creds.json
        credentials_path = "ga_creds.json"
        if os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=GA_SCOPES
            )
        elif settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            value = settings.GOOGLE_SERVICE_ACCOUNT_JSON
            if isinstance(value, str) and os.path.isfile(value):
                credentials = service_account.Credentials.from_service_account_file(
                    value, scopes=GA_SCOPES
                )
        elif settings.GOOGLE_APPLICATION_CREDENTIALS:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=GA_SCOPES
            )

        if credentials is None:
            self._client = GAClient()
        else:
            self._client = GAClient(credentials=credentials)
        return self._client

    async def _resolve_property_id(self, report: Report) -> Optional[str]:
        if self._integration and self._integration.property_id:
            return self._integration.property_id
        # Fallback (редкий случай): ищем в БД
        async with SessionLocal() as session:
            repo = IntegrationRepository(session)
            ga = await repo.get_google_analytics_integration_by_company_id(
                report.company_id
            )
            return ga.property_id if ga else None

    async def generate_report(self, report: Report) -> Optional[ReportData]:
        property_id = await self._resolve_property_id(report)
        if not property_id:
            return None

        client = self._get_client()

        # Базовый маппинг источника к измерениям/метрикам GA4
        if report.source == "paid":
            dimensions = [Dimension(name="sessionDefaultChannelGroup")]  # канал
            metrics = [Metric(name="sessions"), Metric(name="totalRevenue")]
        elif report.source == "free":
            dimensions = [Dimension(name="sessionDefaultChannelGroup")]
            metrics = [Metric(name="sessions"), Metric(name="engagedSessions")]
        else:  # all
            dimensions = [Dimension(name="sessionDefaultChannelGroup")]
            metrics = [Metric(name="sessions"), Metric(name="totalRevenue")]

        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=report.date_1, end_date=report.date_2)],
            dimensions=dimensions,
            metrics=metrics,
        )

        response = client.run_report(request)

        headers = ["Канал"] + [m.name for m in metrics]
        rows: list[list] = []
        for row in response.rows:
            channel = row.dimension_values[0].value
            values = [v.value for v in row.metric_values]
            parsed_values = []
            for v in values:
                try:
                    parsed_values.append(float(v))
                except Exception:
                    parsed_values.append(v)
            rows.append([channel, *parsed_values])

        return ReportData(
            headers=headers,
            rows=rows,
            meta_data=[f"Google Analytics 4 ({_GA_VERSION})"],
        )
