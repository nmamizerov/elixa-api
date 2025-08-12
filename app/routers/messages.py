import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_current_user,
    get_current_user_from_query,
    get_chat_service,
    get_message_service,
)
from app.database.models.user import User
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.schemas import chat as chat_schema

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=List[chat_schema.Message])
async def get_messages(
    chat_id: uuid.UUID = Query(..., description="ID чата для получения сообщений"),
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    message_service: MessageService = Depends(get_message_service),
):
    """Получает список сообщений для указанного чата"""
    # Проверяем, что пользователь имеет доступ к чату
    await chat_service.get_chat_by_id_for_user(chat_id=chat_id, user=current_user)

    # Получаем сообщения
    return await message_service.get_messages_by_chat_id(chat_id)


@router.post(
    "", response_model=chat_schema.Message, status_code=status.HTTP_201_CREATED
)
async def create_message(
    message_request: chat_schema.MessageRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    message_service: MessageService = Depends(get_message_service),
):
    """
    Создает новое сообщение.

    - Если role == "user", создается только пользовательское сообщение
    - Если role == "assistant", запускается обработка через AI ассистента
    """
    # Проверяем, что пользователь имеет доступ к чату
    await chat_service.get_chat_by_id_for_user(
        chat_id=message_request.chat_id, user=current_user
    )

    # Валидация роли
    if message_request.role not in ["user", "assistant"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Роль должна быть 'user' или 'assistant'",
        )

    # Создаем сообщение через сервис
    return await message_service.create_message(
        chat_id=message_request.chat_id,
        message_request=message_request,
        user=current_user,
    )


@router.get("/stream", status_code=status.HTTP_200_OK)
async def stream_agent_message(
    parent_id: uuid.UUID,
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user_from_query),
    chat_service: ChatService = Depends(get_chat_service),
    message_service: MessageService = Depends(get_message_service),
):
    """
    Стримит ответ агента в реальном времени.

    Использует Server-Sent Events (SSE) для передачи промежуточных результатов
    работы агента, включая:
    - Начало обработки
    - Размышления агента
    - Использование инструментов
    - Промежуточные результаты
    - Финальный ответ

    Returns:
        StreamingResponse: Поток событий в формате SSE
    """
    # Проверяем, что пользователь имеет доступ к чату
    await chat_service.get_chat_by_id_for_user(chat_id=chat_id, user=current_user)

    # Создаем генератор стриминга
    async def generate_stream():
        async for event in message_service.stream_agent_response(
            chat_id=chat_id,
            parent_id=parent_id,
            user=current_user,
        ):
            yield event

    # Возвращаем StreamingResponse с корректными заголовками для SSE
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )
