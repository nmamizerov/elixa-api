import asyncio
from typing import Dict, List, Optional, Any
from loguru import logger
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.oauth2 import service_account
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
    RunRealtimeReportRequest,
)
import os

from app.database.models.integration import GoogleAnalyticsIntegration


class GoogleAnalyticsClient:
    """Клиент для работы с API Google Analytics"""

    def __init__(self):
        pass

    def _get_client(
        self, google_analytics_integration: GoogleAnalyticsIntegration
    ) -> Optional[BetaAnalyticsDataClient]:
        """Получение клиента Google Analytics для интеграции"""
        try:
            # Используем service account из ga_creds.json
            credentials_path = "ga_creds.json"
            if os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                return BetaAnalyticsDataClient(credentials=credentials)
            else:
                logger.error(f"Файл {credentials_path} не найден")
                return None
        except Exception as e:
            logger.error(f"Ошибка при создании GA клиента: {str(e)}")
            return None

    def _validate_integration_setup(
        self, google_analytics_integration: GoogleAnalyticsIntegration
    ) -> None:
        """Проверка, что интеграция настроена для работы с Google Analytics"""
        if not google_analytics_integration:
            raise ValueError("Google Analytics интеграция не указана")

        if not google_analytics_integration.property_id:
            raise ValueError(
                "Property ID не настроен в интеграции Google Analytics. Необходимо указать Property ID."
            )

        if not google_analytics_integration.is_active:
            raise ValueError("Интеграция Google Analytics неактивна")

    async def get_ga_data(
        self,
        metrics: List[str],
        dimensions: List[str],
        start_date: str,
        end_date: str,
        google_analytics_integration: GoogleAnalyticsIntegration,
        limit: int = 100,
        realtime: bool = False,
    ) -> Dict[str, Any]:
        """
        Основной метод для получения данных из Google Analytics

        Args:
            metrics: список метрик GA4
            dimensions: список измерений GA4
            start_date: начальная дата в формате YYYY-MM-DD
            end_date: конечная дата в формате YYYY-MM-DD
            google_analytics_integration: интеграция GA
            limit: лимит записей
            realtime: использовать realtime API

        Returns:
            Словарь с данными из GA
        """
        try:
            # Валидация настроек интеграции
            self._validate_integration_setup(google_analytics_integration)

            # Получаем клиента
            client = self._get_client(google_analytics_integration)
            if not client:
                return {"error": "Не удалось создать GA клиент", "status": "error"}

            property_id = google_analytics_integration.property_id

            if realtime:
                data = await self._get_realtime_data(
                    client, property_id, metrics, dimensions, limit
                )
            else:
                data = await self._get_report_data(
                    client,
                    property_id,
                    metrics,
                    dimensions,
                    start_date,
                    end_date,
                    limit,
                )

            return {
                "data": data,
                "status": "success",
                "property_id": property_id,
                "period": f"{start_date} - {end_date}" if not realtime else "realtime",
            }

        except Exception as e:
            logger.error(f"Ошибка при получении данных GA: {str(e)}")
            return {"error": str(e), "status": "error"}

    async def _get_report_data(
        self,
        client: BetaAnalyticsDataClient,
        property_id: str,
        metrics: List[str],
        dimensions: List[str],
        start_date: str,
        end_date: str,
        limit: int,
    ) -> Dict[str, Any]:
        """Получает исторические данные из GA"""

        # Создаем объекты метрик
        ga_metrics = [Metric(name=metric) for metric in metrics]

        # Создаем объекты измерений
        ga_dimensions = [Dimension(name=dimension) for dimension in dimensions]

        # Создаем запрос
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=ga_dimensions,
            metrics=ga_metrics,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit,
        )

        # Выполняем запрос
        response = client.run_report(request=request)

        # Обрабатываем результат
        result = {
            "rows": [],
            "metadata": {
                "property_id": property_id,
                "date_range": f"{start_date} - {end_date}",
                "total_rows": len(response.rows),
                "metrics": metrics,
                "dimensions": dimensions,
            },
        }

        # Извлекаем данные из ответа
        for row in response.rows:
            row_data = {}

            # Добавляем значения измерений
            for i, dimension_value in enumerate(row.dimension_values):
                dimension_name = dimensions[i]
                row_data[dimension_name] = dimension_value.value

            # Добавляем значения метрик
            for i, metric_value in enumerate(row.metric_values):
                metric_name = metrics[i]
                row_data[metric_name] = metric_value.value

            result["rows"].append(row_data)

        return result

    async def _get_realtime_data(
        self,
        client: BetaAnalyticsDataClient,
        property_id: str,
        metrics: List[str],
        dimensions: List[str],
        limit: int,
    ) -> Dict[str, Any]:
        """Получает данные в реальном времени из GA"""

        # Создаем объекты метрик для realtime
        ga_metrics = [Metric(name=metric) for metric in metrics]

        # Создаем объекты измерений для realtime
        ga_dimensions = [Dimension(name=dimension) for dimension in dimensions]

        # Создаем запрос для realtime данных
        request = RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            dimensions=ga_dimensions,
            metrics=ga_metrics,
            limit=limit,
        )

        # Выполняем запрос
        response = client.run_realtime_report(request=request)

        # Обрабатываем результат
        result = {
            "rows": [],
            "metadata": {
                "property_id": property_id,
                "data_type": "realtime",
                "total_rows": len(response.rows),
                "metrics": metrics,
                "dimensions": dimensions,
            },
        }

        # Извлекаем данные из ответа
        for row in response.rows:
            row_data = {}

            # Добавляем значения измерений
            for i, dimension_value in enumerate(row.dimension_values):
                dimension_name = dimensions[i]
                row_data[dimension_name] = dimension_value.value

            # Добавляем значения метрик
            for i, metric_value in enumerate(row.metric_values):
                metric_name = metrics[i]
                row_data[metric_name] = metric_value.value

            result["rows"].append(row_data)

        return result


# Создаем глобальный экземпляр клиента
ga_client = GoogleAnalyticsClient()


class GoogleAnalyticsIntegrationAdapter:
    """Адаптер для интеграции с Google Analytics API по аналогии с YM"""

    def __init__(
        self, credentials_path: Optional[str] = None, property_id: Optional[str] = None
    ):
        self.property_id = property_id
        self.credentials_path = credentials_path or "ga_creds.json"
        self._data_client = None

        # Инициализируем клиентов
        self._init_clients()

    def _init_clients(self):
        """Инициализирует клиентов Google Analytics"""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                # Используем service account из ga_creds.json
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                self._data_client = BetaAnalyticsDataClient(credentials=credentials)
            else:
                logger.error(f"Файл {self.credentials_path} не найден")
                self._data_client = None

        except Exception as e:
            logger.error(f"Ошибка инициализации GA клиентов: {str(e)}")
            self._data_client = None

    def get_client(self) -> Optional[BetaAnalyticsDataClient]:
        """Возвращает клиент для работы с данными"""
        return self._data_client

    def is_connected(self) -> bool:
        """Проверяет подключение к Google Analytics"""
        return self._data_client is not None
