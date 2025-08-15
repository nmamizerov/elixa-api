import asyncio
from typing import List, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field
from app.adapters.google_analytics.client import ga_client


class GoogleAnalyticsDataTool(BaseTool):
    """Инструмент для получения данных из Google Analytics"""

    name: str = "get_ga_data"
    description: str = """Используй этот инструмент для получения данных из Google Analytics.
    ВАЖНО: Перед использованием этого инструмента обязательно вызови сначала parse_dates и get_ga_params!
    
    Входные параметры (все обязательные):
    - metrics: список метрик (например, ['activeUsers', 'sessions'])
    - dimensions: список измерений (например, ['date', 'country'])
    - start_date: начальная дата в формате YYYY-MM-DD
    - end_date: конечная дата в формате YYYY-MM-DD
    - limit: максимальное количество строк (по умолчанию 100)
    - realtime: использовать realtime данные (по умолчанию False)
    
    Возвращает: данные из Google Analytics в формате JSON"""

    googleAnalyticsIntegration: Any = Field(default=None)

    def __init__(self, googleAnalyticsIntegration=None):
        super().__init__()
        self.googleAnalyticsIntegration = googleAnalyticsIntegration

    def _run(
        self,
        metrics: List[str],
        dimensions: List[str],
        start_date: str,
        end_date: str,
        limit: int = 100,
        realtime: bool = False,
    ) -> Dict[str, Any]:
        """Синхронная версия для совместимости"""
        return asyncio.run(
            self._arun(metrics, dimensions, start_date, end_date, limit, realtime)
        )

    async def _arun(
        self,
        metrics: List[str],
        dimensions: List[str],
        start_date: str,
        end_date: str,
        limit: int = 100,
        realtime: bool = False,
    ) -> Dict[str, Any]:
        """Выполняет запрос к Google Analytics"""

        try:
            if not self.googleAnalyticsIntegration:
                return {
                    "error": "Google Analytics интеграция не указана",
                    "status": "error",
                }

            # Используем новый ga_client для получения данных
            ga_response = await ga_client.get_ga_data(
                metrics=metrics,
                dimensions=dimensions,
                start_date=start_date,
                end_date=end_date,
                google_analytics_integration=self.googleAnalyticsIntegration,
                limit=limit,
                realtime=realtime,
            )

            return ga_response

        except Exception as e:
            return {"error": str(e), "status": "error"}
