from app.database.models.integration import YandexMetrikaIntegration
from app.database.repositories.integration_repository import IntegrationRepository
from app.adapters.y_metrika.client import metrika_client


class YandexMetrikaService:

    def __init__(self, integration_repo: IntegrationRepository):
        self.integration_repo = integration_repo

    async def sync_data(self, integration: YandexMetrikaIntegration):
        """Синхронизация данных из Яндекс.Метрики"""
        client = metrika_client
        goals = await client.get_goals(integration)
        print("MEMEMEM")
        print(goals["goals"])
        await self.integration_repo.update_yandex_metrika_integration(
            integration, goals=goals["goals"]
        )
        return True
