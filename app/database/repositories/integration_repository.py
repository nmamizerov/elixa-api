import uuid
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.integration import (
    YandexMetrikaIntegration,
    GoogleAnalyticsIntegration,
)


class IntegrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_yandex_metrika_integration_by_company_id(
        self, company_id: uuid.UUID
    ) -> Optional[YandexMetrikaIntegration]:
        """Получение интеграции по ID с проверкой принадлежности компании"""
        query = select(YandexMetrikaIntegration).where(
            YandexMetrikaIntegration.company_id == company_id,
        )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def create_yandex_metrika_integration(
        self,
        company_id: uuid.UUID,
        counter_id: int,
        token: str,
    ) -> YandexMetrikaIntegration:
        """Создание интеграции с Яндекс.Метрикой"""
        integration = YandexMetrikaIntegration(
            company_id=company_id,
            is_active=True,
            counter_id=counter_id,
            token=token,
        )

        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(integration)

        return integration

    async def deactivate_yandex_metrika_integration(
        self, integration_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        """Деактивация интеграции"""
        query = select(YandexMetrikaIntegration).where(
            YandexMetrikaIntegration.id == integration_id,
            YandexMetrikaIntegration.company_id == company_id,
        )

        result = await self.db.execute(query)
        integration = result.scalars().first()

        if not integration:
            return False

        integration.is_active = False
        await self.db.commit()

        return True

    async def update_yandex_metrika_integration(
        self, integration: YandexMetrikaIntegration, **kwargs
    ) -> bool:
        """Обновление интеграции с Яндекс.Метрикой"""

        query = (
            update(YandexMetrikaIntegration)
            .where(
                YandexMetrikaIntegration.id == integration.id,
            )
            .values(**kwargs)
        )
        await self.db.execute(query)
        await self.db.commit()

    async def get_google_analytics_integration_by_company_id(
        self, company_id: uuid.UUID
    ) -> Optional[GoogleAnalyticsIntegration]:
        query = select(GoogleAnalyticsIntegration).where(
            GoogleAnalyticsIntegration.company_id == company_id,
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def create_google_analytics_integration(
        self,
        company_id: uuid.UUID,
        property_id: str,
    ) -> GoogleAnalyticsIntegration:
        integration = GoogleAnalyticsIntegration(
            company_id=company_id,
            is_active=True,
            property_id=property_id,
        )
        self.db.add(integration)
        await self.db.commit()
        await self.db.refresh(integration)
        return integration

    async def deactivate_google_analytics_integration(
        self, integration_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        query = select(GoogleAnalyticsIntegration).where(
            GoogleAnalyticsIntegration.id == integration_id,
            GoogleAnalyticsIntegration.company_id == company_id,
        )
        result = await self.db.execute(query)
        integration = result.scalars().first()
        if not integration:
            return False
        integration.is_active = False
        await self.db.commit()
        return True
