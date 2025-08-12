from typing import Literal, Optional

from app.adapters.y_metrika.client import YandexMetrikaClient
from app.schemas.integration import YandexMetrikaIntegration
from .base import BaseReportGenerator
from .paid_report_generator import PaidReportGenerator
from .free_report_generator import FreeReportGenerator
from .direct_report_generator import DirectReportGenerator


class ReportGeneratorFactory:
    """Фабрика для создания генераторов отчетов"""

    def __init__(
        self,
        metrika_client: YandexMetrikaClient,
        yandex_metrika_integration: YandexMetrikaIntegration,
    ):
        self.metrika_client = metrika_client
        self.yandex_metrika_integration = yandex_metrika_integration
        self._paid_generator: Optional[PaidReportGenerator] = None
        self._free_generator: Optional[FreeReportGenerator] = None
        self._direct_generator: Optional[DirectReportGenerator] = None

    def get_generator(
        self, source: Literal["paid", "free", "all", "direct"]
    ) -> BaseReportGenerator:
        """Получение генератора по типу источника"""
        if source == "paid":
            return self._get_paid_generator()
        elif source == "free":
            return self._get_free_generator()
        elif source == "all":
            # Для "all" используем free generator с поддержкой включения данных директа
            return self._get_free_generator()
        elif source == "direct":
            return self._get_direct_generator()

    def _get_paid_generator(self) -> PaidReportGenerator:
        """Получение генератора платных отчетов"""
        if self._paid_generator is None:
            self._paid_generator = PaidReportGenerator(
                self.metrika_client, self.yandex_metrika_integration
            )
        return self._paid_generator

    def _get_free_generator(self) -> FreeReportGenerator:
        """Получение генератора бесплатных отчетов"""
        if self._free_generator is None:
            self._free_generator = FreeReportGenerator(
                self.metrika_client, self.yandex_metrika_integration
            )
        return self._free_generator

    def _get_direct_generator(
        self, attribution: str = "CROSS_DEVICE_LAST_SIGNIFICANT"
    ) -> DirectReportGenerator:
        """Получение генератора Direct отчетов"""
        if self._direct_generator is None:
            self._direct_generator = DirectReportGenerator(
                self.metrika_client,
                self.yandex_metrika_integration,
                attribution,
            )
        return self._direct_generator

    def create_generator(
        self,
        source: Literal["paid", "free", "all", "direct"],
        attribution: str = "CROSS_DEVICE_LAST_SIGNIFICANT",
    ) -> BaseReportGenerator:
        """Создание нового экземпляра генератора (без кеширования)"""
        if source == "paid":
            return PaidReportGenerator(
                self.metrika_client, self.yandex_metrika_integration
            )
        elif source == "free":
            return FreeReportGenerator(
                self.metrika_client, self.yandex_metrika_integration
            )
        elif source == "all":
            # Для "all" возвращаем FreeReportGenerator, который может включать данные директа
            return FreeReportGenerator(
                self.metrika_client, self.yandex_metrika_integration
            )
        elif source == "direct":
            return DirectReportGenerator(
                self.metrika_client, self.yandex_metrika_integration, attribution
            )
        else:
            raise ValueError(f"Unknown report source: {source}")

    def clear_cache(self):
        """Очистка кеша генераторов"""
        self._paid_generator = None
        self._free_generator = None
        self._direct_generator = None
