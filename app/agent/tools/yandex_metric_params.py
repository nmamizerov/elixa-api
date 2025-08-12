from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
import asyncio

from app.core.config import settings
from app.agent.models import MetrikaDataNodeResponseFormat
from app.agent.prompts.get_metrika_data import GET_METRIKA_DATA_PARAMS_PROMPT


class YandexMetrikaParamsTool(BaseTool):
    """Инструмент для определения параметров запроса к Яндекс.Метрике"""

    name: str = "get_metrika_params"
    description: str = """Используй этот инструмент для определения нужных метрик и измерений 
    для запроса к Яндекс.Метрике на основе вопроса пользователя.
    Входные данные: текст запроса пользователя
    Возвращает: структуру с dimensions и metrics для API Яндекс.Метрики"""

    def _run(self, user_message: str) -> Dict[str, Any]:
        """Синхронная версия для совместимости"""
        return asyncio.run(self._arun(user_message))

    async def _arun(self, user_message: str) -> Dict[str, Any]:
        """Определяет параметры для запроса к Яндекс.Метрике"""
        prompt = GET_METRIKA_DATA_PARAMS_PROMPT.replace("{user_message}", user_message)

        llm = ChatOpenAI(
            model="gpt-4o-mini", temperature=0.7, openai_api_key=settings.OPENAI_API_KEY
        )

        llm = llm.with_structured_output(MetrikaDataNodeResponseFormat)
        response = await llm.ainvoke(prompt)

        return {
            "dimensions": response.dimensions,
            "metrics": response.metrics,
            "status": "success",
        }
