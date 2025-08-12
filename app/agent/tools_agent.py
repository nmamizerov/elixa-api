import uuid
from typing import List, Dict, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
import asyncio

from app.agent.tools.dates_parse_tool import DateParserTool
from app.agent.tools.yandex_metric import YandexMetrikaDataTool
from app.agent.tools.yandex_metric_params import YandexMetrikaParamsTool
from app.core.config import settings


class MarketingAgent:
    """Tool-based агент для маркетинговой аналитики"""

    def __init__(self, yandexMetrikaIntegration=None):
        self.yandexMetrikaIntegration = yandexMetrikaIntegration
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", temperature=0.7, openai_api_key=settings.OPENAI_API_KEY
        )

        # Создаем инструменты
        self.tools = [
            DateParserTool(),
            YandexMetrikaParamsTool(),
            YandexMetrikaDataTool(yandexMetrikaIntegration=yandexMetrikaIntegration),
        ]

        # Создаем промпт для агента
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # Создаем агента
        self.agent = create_openai_tools_agent(
            llm=self.llm, tools=self.tools, prompt=self.prompt
        )

        # Создаем executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True,
        )

    def _get_system_prompt(self) -> str:
        """Возвращает системный промпт для агента"""
        return """Ты — AI-агент для анализа веб-аналитики по имени Pulse. 
        Твоя задача — помочь пользователю с анализом данных из Яндекс.Метрики, 
        отвечать на вопросы о трафике, конверсии, поведении пользователей и давать практические рекомендации.

        У тебя есть доступ к следующим инструментам:
        1. parse_dates - для извлечения дат из запроса пользователя
        2. get_metrika_params - для определения нужных метрик и измерений
        3. get_metrika_data - для получения данных из Яндекс.Метрики

        ВАЖНЫЕ ПРАВИЛА:
        - Если пользователь спрашивает про данные из Яндекс.Метрики, ОБЯЗАТЕЛЬНО используй инструменты в правильном порядке:
          1) Сначала parse_dates для определения периода
          2) Затем get_metrika_params для определения нужных метрик  
          3) Наконец get_metrika_data для получения данных
        - Если пользователь задает общий вопрос без запроса данных, отвечай на основе своих знаний
        - Всегда отвечай на русском языке
        - Будь конкретным и полезным в своих советах
        - Если получил данные из Метрики, обязательно проанализируй их и дай рекомендации

        Примеры вопросов, требующих данных:
        - "Покажи трафик за последнюю неделю"
        - "Какие источники трафика самые эффективные?"
        - "Сколько у нас было посетителей вчера?"
        
        Примеры общих вопросов:
        - "Как улучшить конверсию сайта?"
        - "Что такое показатель отказов?"
        - "Привет, как дела?"
        """

    async def process_message(
        self, user_message: str, chat_history: List[Dict] | None = None
    ) -> str:
        """Обрабатывает сообщение пользователя"""
        if chat_history is None:
            chat_history = []

        # Конвертируем историю чата в формат для LangChain
        formatted_history = []
        for msg in chat_history:
            if msg["role"] == "user":
                formatted_history.append(("user", msg["content"]))
            elif msg["role"] == "assistant":
                formatted_history.append(("assistant", msg["content"]))

        try:
            result = await self.agent_executor.ainvoke(
                {"input": user_message, "chat_history": formatted_history}
            )

            return result["output"]

        except Exception as e:
            return f"Извини, произошла ошибка при обработке твоего запроса: {str(e)}"

    async def stream_message(
        self, user_message: str, chat_history: List[Dict] | None = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Стримит обработку сообщения пользователя с промежуточными результатами

        Yields:
            Dict: Словарь с типом события и данными
            - {"type": "start", "message": "Начинаю обработку..."}
            - {"type": "thinking", "message": "Анализирую запрос..."}
            - {"type": "tool_start", "tool_name": "parse_dates", "message": "Извлекаю даты..."}
            - {"type": "tool_result", "tool_name": "parse_dates", "result": {...}}
            - {"type": "step", "content": "Частичный ответ агента"}
            - {"type": "final", "content": "Финальный ответ"}
            - {"type": "error", "message": "Описание ошибки"}
        """
        if chat_history is None:
            chat_history = []

        # Конвертируем историю чата в формат для LangChain
        formatted_history = []
        for msg in chat_history:
            if msg["role"] == "user":
                formatted_history.append(("user", msg["content"]))
            elif msg["role"] == "assistant":
                formatted_history.append(("assistant", msg["content"]))

        try:
            # Отправляем событие начала обработки
            yield {"type": "start", "message": "🚀 Начинаю обработку вашего запроса..."}

            # Используем стриминг агента
            async for chunk in self.agent_executor.astream(
                {"input": user_message, "chat_history": formatted_history},
                {"metadata": {"stream_mode": "values"}},
            ):

                # Обрабатываем различные типы событий от агента
                if "messages" in chunk:
                    messages = chunk["messages"]
                    if messages:
                        last_message = messages[-1]

                        if (
                            hasattr(last_message, "tool_calls")
                            and last_message.tool_calls
                        ):
                            for tool_call in last_message.tool_calls:
                                tool_name = tool_call.get("name", "unknown")
                                yield {
                                    "type": "tool_start",
                                    "tool_name": tool_name,
                                    "args": tool_call.get("args", {}),
                                    "message": f"🔧 Использую инструмент: {tool_name}",
                                }

                        # Если это результат инструмента
                        elif (
                            hasattr(last_message, "type")
                            and last_message.type == "tool"
                        ):
                            tool_name = getattr(last_message, "name", "unknown")
                            yield {
                                "type": "tool_result",
                                "tool_name": tool_name,
                                "message": f"✅ Получил результат от {tool_name}",
                            }

                # Если это промежуточные шаги
                elif "intermediate_steps" in chunk:
                    steps = chunk["intermediate_steps"]
                    for step in steps:
                        if len(step) >= 2:
                            action, result = step[0], step[1]
                            if hasattr(action, "tool"):
                                yield {
                                    "type": "tool_result",
                                    "tool_name": action.tool,
                                    "message": f"✅ Инструмент {action.tool} выполнен успешно",
                                }

            # Получаем финальный результат
            yield {"type": "thinking", "message": "🎯 Формирую финальный ответ..."}

            result = await self.agent_executor.ainvoke(
                {"input": user_message, "chat_history": formatted_history}
            )

            yield {"type": "final", "content": result["output"]}

        except Exception as e:
            yield {
                "type": "error",
                "message": f"❌ Произошла ошибка при обработке запроса: {str(e)}",
            }
