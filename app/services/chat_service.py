import uuid
from fastapi import HTTPException, status

from app.database.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatCreate
from app.database.models.user import User


class ChatService:
    def __init__(self, chat_repo: ChatRepository):
        self.chat_repo = chat_repo

    async def get_user_chats(self, user_id: uuid.UUID):
        """Получает список чатов пользователя без сообщений"""
        return await self.chat_repo.get_chats_by_user(user_id=user_id)

    async def create_new_chat(self, chat_in: ChatCreate, user: User):
        return await self.chat_repo.create_chat(chat=chat_in, user=user)

    async def get_chat_by_id_for_user(self, chat_id: uuid.UUID, user: User):
        """Получает чат по ID без сообщений с проверкой доступа"""
        db_chat = await self.chat_repo.get_chat_by_id(chat_id=chat_id)
        if not db_chat or db_chat.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        return db_chat

    async def delete_chat(self, chat_id: uuid.UUID, user: User):
        """Удаляет чат по ID с проверкой доступа"""
        db_chat = await self.chat_repo.get_chat_by_id(chat_id=chat_id)
        if not db_chat or db_chat.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        await self.chat_repo.delete_chat(chat_id=chat_id)
