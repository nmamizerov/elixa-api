import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models.chat import Chat
from app.database.models.user import User
from app.schemas.chat import ChatCreate


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_chats_by_user(self, user_id: uuid.UUID) -> list[Chat]:
        result = await self.db.execute(
            select(Chat)
            .filter(Chat.user_id == user_id)
            .order_by(Chat.created_at.desc())
        )
        return result.scalars().all()

    async def create_chat(self, chat: ChatCreate, user: User) -> Chat:
        db_chat = Chat(**chat.model_dump(), user_id=user.id)
        self.db.add(db_chat)
        await self.db.commit()
        await self.db.flush()

        result = await self.db.execute(select(Chat).where(Chat.id == db_chat.id))
        return result.scalars().one()

    async def get_chat_by_id(self, chat_id: uuid.UUID) -> Chat | None:
        """Получает чат по ID без загрузки сообщений"""
        result = await self.db.execute(select(Chat).filter(Chat.id == chat_id))
        return result.scalars().first()

    async def delete_chat(self, chat_id: uuid.UUID) -> None:
        """Удаляет чат по ID"""
        result = await self.db.execute(select(Chat).filter(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if chat:
            await self.db.delete(chat)
            await self.db.commit()
