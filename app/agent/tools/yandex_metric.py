import asyncio
from typing import List, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field


class YandexMetrikaDataTool(BaseTool):
    """Инструмент для получения данных из Яндекс.Метрики"""

    name: str = "get_metrika_data"
    description: str = """Используй этот инструмент для получения данных из Яндекс.Метрики.
    ВАЖНО: Перед использованием этого инструмента обязательно вызови сначала parse_dates и get_metrika_params!
    
    Входные параметры (все обязательные):
    - dimensions: список измерений (например, ['ym:s:date'])  
    - metrics: список метрик (например, ['ym:s:visits'])
    - date_1: начальная дата в формате YYYY-MM-DD
    - date_2: конечная дата в формате YYYY-MM-DD
    
    Возвращает: данные из Яндекс.Метрики в формате JSON"""

    yandexMetrikaIntegration: Any = Field(default=None)

    def __init__(self, yandexMetrikaIntegration=None):
        super().__init__()
        self.yandexMetrikaIntegration = yandexMetrikaIntegration

    def _run(
        self, dimensions: List[str], metrics: List[str], date_1: str, date_2: str
    ) -> Dict[str, Any]:
        """Синхронная версия для совместимости"""
        return asyncio.run(self._arun(dimensions, metrics, date_1, date_2))

    async def _arun(
        self, dimensions: List[str], metrics: List[str], date_1: str, date_2: str
    ) -> Dict[str, Any]:
        """Получает данные из Яндекс.Метрики"""
        try:
            from app.adapters.y_metrika.client import metrika_client

            if not self.yandexMetrikaIntegration:
                return {"error": "Компания не указана", "status": "error"}

            metrika_response = await metrika_client.get_metrika_data(
                dimensions=dimensions,
                metrics=metrics,
                date_1=date_1,
                date_2=date_2,
                yandexMetrikaIntegration=self.yandexMetrikaIntegration,
            )

            return {
                "data": metrika_response or {},
                "status": "success",
                "period": f"{date_1} - {date_2}",
            }

        except Exception as e:
            return {"error": str(e), "status": "error"}
