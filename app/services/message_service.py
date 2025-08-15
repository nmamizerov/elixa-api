import uuid
from typing import List, AsyncGenerator
import json
from datetime import datetime

from app.agent.tools_agent import MarketingAgent
from app.database.repositories.message_repository import MessageRepository
from app.database.repositories.chat_repository import ChatRepository
from app.database.repositories.company_repository import CompanyRepository
from app.schemas.chat import MessageCreate, MessageRequest
from app.schemas.company import Company
from app.database.models.chat import Message
from app.database.models.user import User
from app.database.repositories.integration_repository import IntegrationRepository


class MessageService:
    def __init__(
        self,
        message_repo: MessageRepository,
        chat_repo: ChatRepository,
        company_repo: CompanyRepository,
        integration_repo: IntegrationRepository,
    ):
        self.message_repo = message_repo
        self.chat_repo = chat_repo
        self.company_repo = company_repo
        self.integration_repo = integration_repo

    async def create_user_message(self, chat_id: uuid.UUID, message_in: MessageCreate):
        """Создает пользовательское сообщение и возвращает его"""
        return await self.message_repo.create_chat_message(
            message=message_in, chat_id=chat_id
        )

    async def get_messages_by_chat_id(self, chat_id: uuid.UUID) -> List[Message]:
        """Получает все сообщения чата"""
        return await self.message_repo.get_messages_by_chat_id(chat_id)

    async def create_message(
        self,
        chat_id: uuid.UUID,
        message_request: MessageRequest,
        user: User,
    ) -> Message:
        """
        Создает новое сообщение с полной логикой обработки.

        1. Получаем parent_message если есть
        2. Вычисляем path: parent_message.path + parent_id или []
        3. Вычисляем content: для assistant - запрос к LLM, для user - из DTO
        """
        # 1. Получаем parent_message если есть
        parent_message = None
        if message_request.parent_id:
            parent_message = await self.message_repo.get_message_by_id(
                message_request.parent_id
            )

        # 2. Вычисляем path
        path = []
        if parent_message:
            path = parent_message.path + [str(message_request.parent_id)]

        # 3. Вычисляем content в зависимости от роли
        if message_request.role == "assistant":
            # Получаем историю чата для контекста
            chat_history = []
            if parent_message:
                history_messages = await self.message_repo.get_messages_by_ids(
                    parent_message.path
                )
                chat_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in history_messages
                ]

            # Получаем компанию пользователя
            yandex_metrika_integration = await self.integration_repo.get_yandex_metrika_integration_by_company_id(
                user.current_company_id
            )
            google_analytics_integration = await self.integration_repo.get_google_analytics_integration_by_company_id(
                user.current_company_id
            )

            # Обрабатываем через агента
            agent = MarketingAgent(
                yandexMetrikaIntegration=yandex_metrika_integration,
                googleAnalyticsIntegration=google_analytics_integration,
            )
            content = await agent.process_message(parent_message.content, chat_history)
        else:
            # Для пользовательского сообщения берем content из DTO
            content = message_request.content

        # Создаем сообщение
        message_create = MessageCreate(
            role=message_request.role,
            content=content,
            parent_id=message_request.parent_id,
            path=path,
        )

        return await self.message_repo.create_chat_message(
            message=message_create, chat_id=chat_id
        )

    async def stream_agent_response(
        self, chat_id: uuid.UUID, parent_id: uuid.UUID, user: User
    ) -> AsyncGenerator[str, None]:
        """
        Стримит ответ агента в формате Server-Sent Events

        Args:
            chat_id: ID чата
            parent_id: ID родительского сообщения
            user_id: ID пользователя

        Yields:
            str: События в формате SSE (data: {json}\n\n)
        """
        # Список для сбора всех событий стриминга
        events = []
        assistant_message: Message = None

        try:
            # 1. Создаем пользовательское сообщение

            parent_message = await self.message_repo.get_message_by_id(parent_id)
            # 2. Вычисляем path
            path = []
            if parent_message:
                path = parent_message.path + [str(parent_id)]

            # 2. Получаем историю чата для контекста
            chat_history = []
            if parent_message:
                history_messages = await self.message_repo.get_messages_by_ids(
                    parent_message.path
                )
                chat_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in history_messages
                ]

            yandex_metrika_integration = await self.integration_repo.get_yandex_metrika_integration_by_company_id(
                user.current_company_id
            )
            google_analytics_integration = await self.integration_repo.get_google_analytics_integration_by_company_id(
                user.current_company_id
            )
            # Обрабатываем через агента
            agent = MarketingAgent(
                yandexMetrikaIntegration=yandex_metrika_integration,
                googleAnalyticsIntegration=google_analytics_integration,
            )

            assistant_content = ""

            assistant_message_create = MessageCreate(
                role="assistant",
                content=assistant_content,
                parent_id=parent_id,
                path=path,
            )

            assistant_message: Message = await self.message_repo.create_chat_message(
                message=assistant_message_create, chat_id=chat_id
            )

            yield f"data: {json.dumps({'type': 'message_add', 'data': assistant_message.to_dict()}, ensure_ascii=False)}\n\n"

            async for event in agent.stream_message(
                parent_message.content, chat_history
            ):

                if not event.get("type") == "final":
                    event_data = {"timestamp": datetime.now().isoformat(), **event}

                    # Добавляем событие в список
                    events.append(event_data)

                    # Отправляем событие в формате SSE
                    yield f"data: {json.dumps({
                        "type": "message_add_event",
                        "data": {
                            "id": str(assistant_message.id),
                            "data": event_data
                        }
                    }, ensure_ascii=False)}\n\n"
                # Собираем контент для финального сообщения
                if event.get("type") == "final":
                    assistant_content = event.get("content", "")

            # 5. Создаем сообщение агента в базе данных после завершения стрима
            if assistant_content:

                # Отправляем финальное событие с ID созданного сообщения
                final_event = {
                    "type": "message_created",
                    "timestamp": datetime.now().isoformat(),
                    "data": {"id": str(assistant_message.id)},
                }

                # Добавляем финальное событие в список
                events.append(final_event)
                await self.message_repo.update_message(
                    assistant_message,
                    data={"events": events},
                    content=assistant_content,
                )
                yield f"data: {json.dumps({**final_event, "data": {"id": str(assistant_message.id), "content": assistant_content}}, ensure_ascii=False)}\n\n"

        except Exception as e:
            # Отправляем событие ошибки
            error_event = {
                "type": "error",
                "message": f"Произошла ошибка: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

            # Добавляем событие ошибки в список
            events.append(error_event)
            if assistant_message:
                await self.message_repo.update_message(
                    assistant_message, {"events": events}
                )

            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
