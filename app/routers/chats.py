import uuid
from fastapi import APIRouter, Depends, status
from typing import List

from app.dependencies import (
    get_current_user,
    get_chat_service,
)
from app.database.models.user import User
from app.services.chat_service import ChatService
from app.schemas import chat as chat_schema

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", response_model=List[chat_schema.Chat])
async def read_chats(
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return await chat_service.get_user_chats(user_id=current_user.id)


@router.post("", response_model=chat_schema.Chat, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: chat_schema.ChatCreate,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return await chat_service.create_new_chat(chat_in=chat_in, user=current_user)


@router.get("/{chat_id}", response_model=chat_schema.Chat)
async def read_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    return await chat_service.get_chat_by_id_for_user(
        chat_id=chat_id, user=current_user
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    await chat_service.delete_chat(chat_id=chat_id, user=current_user)
