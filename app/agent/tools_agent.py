from typing import List, Dict, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.tools.dates_parse_tool import DateParserTool
from app.agent.tools.yandex_metric import YandexMetrikaDataTool
from app.agent.tools.yandex_metric_params import YandexMetrikaParamsTool
from app.agent.tools.google_analytics_data import GoogleAnalyticsDataTool
from app.agent.tools.google_analytics_params import GoogleAnalyticsParamsTool
from app.core.config import settings


class MarketingAgent:
    """Tool-based агент для маркетинговой аналитики"""

    def __init__(self, yandexMetrikaIntegration=None, googleAnalyticsIntegration=None):
        self.yandexMetrikaIntegration = yandexMetrikaIntegration
        self.googleAnalyticsIntegration = googleAnalyticsIntegration
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", temperature=0.7, openai_api_key=settings.OPENAI_API_KEY
        )

        # Создаем инструменты
        self.tools = [
            DateParserTool(),
        ]

        # Добавляем инструменты Яндекс.Метрики если есть интеграция
        if yandexMetrikaIntegration:
            self.tools.extend(
                [
                    YandexMetrikaParamsTool(),
                    YandexMetrikaDataTool(
                        yandexMetrikaIntegration=yandexMetrikaIntegration
                    ),
                ]
            )

        # Добавляем инструменты Google Analytics если есть интеграция
        if googleAnalyticsIntegration:
            self.tools.extend(
                [
                    GoogleAnalyticsParamsTool(),
                    GoogleAnalyticsDataTool(
                        googleAnalyticsIntegration=googleAnalyticsIntegration
                    ),
                ]
            )

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

        available_sources = []
        if self.yandexMetrikaIntegration:
            available_sources.append("Яндекс.Метрика")
        if self.googleAnalyticsIntegration:
            available_sources.append("Google Analytics")

        sources_text = (
            " и ".join(available_sources)
            if available_sources
            else "аналитические системы"
        )

        return f"""
        Ты - AI-агент для маркетинговой аналитики, который работает с данными из {sources_text}.
        
        Доступные источники данных: {sources_text}
        
        Твоя задача:
        1. Анализировать запросы пользователей о маркетинговых метриках
        2. Определять нужные данные и временные периоды
        3. Получать данные из доступных источников
        4. Предоставлять понятные и полезные аналитические отчеты
        
        ВАЖНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ ДЕЙСТВИЙ:
        1. ВСЕГДА сначала используй parse_dates для определения временного периода
        2. Затем используй get_metrika_params (для Яндекс.Метрики) или get_ga_params (для Google Analytics) для определения нужных метрик
        3. Только после этого используй get_metrika_data или get_ga_data для получения данных
        
        Отвечай на русском языке, будь полезным и предоставляй практические рекомендации.
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
