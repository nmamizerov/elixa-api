from __future__ import annotations

from typing import Optional

from app.schemas.integration import YandexMetrikaIntegration, GoogleAnalyticsIntegration
from .base import AnalyticsProvider
from .yandex_provider import YandexMetrikaProvider
from .google_provider import GoogleAnalyticsProvider


class ProviderRegistry:
    """Реестр провайдеров аналитики."""

    def __init__(self):
        self._providers: dict[str, AnalyticsProvider] = {}

    def get_yandex(self, integration: YandexMetrikaIntegration) -> AnalyticsProvider:
        key = f"yandex:{integration.id}"
        provider = self._providers.get(key)
        if provider is None:
            provider = YandexMetrikaProvider(integration)
            self._providers[key] = provider
        return provider

    def get_google(
        self, integration: Optional[GoogleAnalyticsIntegration] = None
    ) -> AnalyticsProvider:
        key = f"google:{integration.id if integration else 'none'}"
        provider = self._providers.get(key)
        if provider is None:
            provider = GoogleAnalyticsProvider(integration)
            self._providers[key] = provider
        return provider

    def clear(self) -> None:
        self._providers.clear()
