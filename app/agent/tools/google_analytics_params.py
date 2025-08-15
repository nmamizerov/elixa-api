from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
import asyncio

from app.core.config import settings
from app.agent.models import MetrikaDataNodeResponseFormat


class GoogleAnalyticsParamsTool(BaseTool):
    """Инструмент для определения нужных метрик и измерений Google Analytics"""

    name: str = "get_ga_params"
    description: str = """Используй этот инструмент для определения нужных метрик и измерений 
    для запроса к Google Analytics на основе вопроса пользователя.
    Входные данные: текст запроса пользователя
    Возвращает: структуру с dimensions и metrics для API Google Analytics"""

    def _run(self, user_query: str) -> Dict[str, Any]:
        """Синхронная версия для совместимости"""
        return asyncio.run(self._arun(user_query))

    async def _arun(self, user_query: str) -> Dict[str, Any]:
        """Определяет параметры для запроса к Google Analytics"""

        # Промпт для анализа GA4 запросов
        ga_prompt = f"""
        Проанализируй запрос пользователя и определи какие метрики и измерения Google Analytics 4 нужны для ответа.

        Запрос пользователя: {user_query}

        Доступные метрики GA4:
        - activeUsers (активные пользователи)
        - newUsers (новые пользователи) 
        - sessions (сессии)
        - screenPageViews (просмотры страниц)
        - bounceRate (показатель отказов)
        - averageSessionDuration (средняя длительность сессии)
        - conversions (конверсии)
        - eventCount (события)
        - totalRevenue (общий доход)
        - purchaseRevenue (доход с покупок)

        Доступные измерения GA4:
        - date (дата)
        - month (месяц)
        - week (неделя)
        - hour (час)
        - country (страна)
        - city (город)
        - region (регион)
        - deviceCategory (категория устройства)
        - browser (браузер)
        - operatingSystem (операционная система)
        - firstUserSource (источник первого посещения)
        - firstUserMedium (канал первого посещения)
        - firstUserDefaultChannelGroup (группа каналов)
        - firstUserCampaignName (название кампании)
        - pagePath (путь страницы)
        - pageTitle (заголовок страницы)
        - eventName (название события)

        Выбери ТОЛЬКО те метрики и измерения, которые нужны для ответа на запрос.
        Если запрос касается временного анализа, обязательно включи date в измерения.
        """

        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                openai_api_key=settings.OPENAI_API_KEY,
            )

            llm = llm.with_structured_output(MetrikaDataNodeResponseFormat)
            response = await llm.ainvoke(ga_prompt)

            return {
                "dimensions": response.dimensions,
                "metrics": response.metrics,
                "status": "success",
                "original_query": user_query,
            }

        except Exception as e:
            # Fallback к базовым метрикам в случае ошибки
            return {
                "dimensions": ["date"],
                "metrics": ["activeUsers", "sessions", "screenPageViews"],
                "status": "success",
                "original_query": user_query,
                "fallback": True,
                "error": str(e),
            }
