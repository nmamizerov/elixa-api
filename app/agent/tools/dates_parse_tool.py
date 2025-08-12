from datetime import datetime
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
import asyncio

from app.core.config import settings
from app.agent.models import DateNodeResponseFormat
from app.agent.prompts.get_dates import GET_DATES_PROMPT


class DateParserTool(BaseTool):
    """Инструмент для парсинга дат из пользовательского запроса"""

    name: str = "parse_dates"
    description: str = """Используй этот инструмент для извлечения дат из запроса пользователя.
    Инструмент определяет временной период для анализа данных.
    Входные данные: текст запроса пользователя
    Возвращает: две даты в формате YYYY-MM-DD (date_1 и date_2)"""

    def _run(self, user_message: str) -> Dict[str, str]:
        """Синхронная версия для совместимости"""
        return asyncio.run(self._arun(user_message))

    async def _arun(self, user_message: str) -> Dict[str, str]:
        """Парсит даты из пользовательского запроса"""
        today = datetime.now().strftime("%Y-%m-%d")

        prompt = GET_DATES_PROMPT.replace("{today}", today).replace(
            "{user_message}", user_message
        )

        llm = ChatOpenAI(
            model="gpt-4o-mini", temperature=0.7, openai_api_key=settings.OPENAI_API_KEY
        )

        llm = llm.with_structured_output(DateNodeResponseFormat)
        response = await llm.ainvoke(prompt)

        return {
            "date_1": response.date_1,
            "date_2": response.date_2,
            "status": "success",
        }
