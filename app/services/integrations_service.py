import uuid
from typing import Optional

from app.database.repositories.integration_repository import IntegrationRepository
from app.schemas.integration import (
    YandexMetrikaIntegrationBase,
    YandexMetrikaIntegrationResponse,
    IntegrationsListResponse,
    GoogleAnalyticsIntegrationBase,
    GoogleAnalyticsIntegrationResponse,
)
from app.services.auth_service import get_password_hash  # Для шифрования токенов
from app.services.integrations.yandex_metrika import YandexMetrikaService


class IntegrationsService:
    """Сервис для работы с интеграциями"""

    def __init__(
        self,
        integration_repo: IntegrationRepository,
        yandex_metrika_service: YandexMetrikaService,
    ):
        self.integration_repo = integration_repo
        self.yandex_metrika_service = yandex_metrika_service

    async def get_company_integrations(
        self, company_id: uuid.UUID
    ) -> IntegrationsListResponse:
        """Получение списка подключенных интеграций компании"""
        integrations = []

        # Яндекс.Метрика
        active_ym_integration = (
            await self.integration_repo.get_yandex_metrika_integration_by_company_id(
                company_id
            )
        )
        if active_ym_integration:
            integrations.append("yandex-metrika")

        # Google Analytics
        active_ga_integration = (
            await self.integration_repo.get_google_analytics_integration_by_company_id(
                company_id
            )
        )
        if active_ga_integration:
            integrations.append("google-analytics")

        return IntegrationsListResponse(integrations=integrations)

    async def get_yandex_metrika_integration_detail(
        self, company_id: uuid.UUID
    ) -> Optional[YandexMetrikaIntegrationResponse]:
        """Получение детальной информации об интеграции Яндекс.Метрики"""
        integration = (
            await self.integration_repo.get_yandex_metrika_integration_by_company_id(
                company_id
            )
        )

        if not integration:
            return None

        return YandexMetrikaIntegrationResponse(
            id=integration.id,
            company_id=integration.company_id,
            is_active=integration.is_active,
            counter_id=integration.counter_id,
            has_token=bool(integration.token),
            token_preview=f"{integration.token[:8]}..." if integration.token else None,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
            goals=integration.goals,
            data=integration.data,
        )

    async def connect_yandex_metrika(
        self, company_id: uuid.UUID, request: YandexMetrikaIntegrationBase
    ) -> YandexMetrikaIntegrationResponse:
        integration = await self.integration_repo.create_yandex_metrika_integration(
            company_id=company_id,
            counter_id=request.counter_id,
            token=request.token,
        )
        await self.yandex_metrika_service.sync_data(integration)
        return await self.get_yandex_metrika_integration_detail(company_id)

    async def disconnect_yandex_metrika_integration(
        self, integration_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        return await self.integration_repo.deactivate_yandex_metrika_integration(
            integration_id, company_id
        )

    async def sync_yandex_metrika_integration(self, company_id: uuid.UUID) -> bool:
        integration = (
            await self.integration_repo.get_yandex_metrika_integration_by_company_id(
                company_id
            )
        )
        return await self.yandex_metrika_service.sync_data(integration)

    # ---- Google Analytics 4 ----
    async def get_google_analytics_integration_detail(
        self, company_id: uuid.UUID
    ) -> Optional[GoogleAnalyticsIntegrationResponse]:
        integration = (
            await self.integration_repo.get_google_analytics_integration_by_company_id(
                company_id
            )
        )
        if not integration:
            return None
        return GoogleAnalyticsIntegrationResponse(
            id=integration.id,
            company_id=integration.company_id,
            is_active=integration.is_active,
            property_id=integration.property_id,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
            data=integration.data,
        )

    async def connect_google_analytics(
        self, company_id: uuid.UUID, request: GoogleAnalyticsIntegrationBase
    ) -> GoogleAnalyticsIntegrationResponse:
        integration = await self.integration_repo.create_google_analytics_integration(
            company_id=company_id,
            property_id=request.property_id,
        )
        # На этом этапе можно выполнить первичную синхронизацию метаданных GA4
        return await self.get_google_analytics_integration_detail(company_id)

    async def disconnect_google_analytics_integration(
        self, integration_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        return await self.integration_repo.deactivate_google_analytics_integration(
            integration_id, company_id
        )
