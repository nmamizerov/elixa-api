import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models.chat import Message
from app.schemas.chat import MessageCreate


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_chat_message(
        self, message: MessageCreate, chat_id: uuid.UUID, data: dict = {}
    ) -> Message:
        # Вычисляем path для нового сообщения только если он не передан
        # Создаем сообщение с вычисленным path
        message_data = message.model_dump()

        db_message = Message(**message_data, chat_id=chat_id, data=data)
        self.db.add(db_message)
        await self.db.commit()
        await self.db.refresh(db_message)
        return db_message

    async def _calculate_message_path(self, parent_id: uuid.UUID | None) -> list[str]:
        """Вычисляет path для сообщения на основе parent_id"""
        if parent_id is None:
            return []

        # Получаем родительское сообщение
        result = await self.db.execute(select(Message).filter(Message.id == parent_id))
        parent_message = result.scalar_one_or_none()

        if parent_message is None:
            return []

        # Формируем path: path родителя + id родителя
        parent_path = parent_message.path or []
        return parent_path + [str(parent_id)]

    async def get_message_by_id(self, message_id: uuid.UUID) -> Message | None:
        """Получает сообщение по ID"""
        result = await self.db.execute(select(Message).filter(Message.id == message_id))
        return result.scalar_one_or_none()

    async def get_messages_by_chat_id(self, chat_id: uuid.UUID) -> List[Message]:
        """Получает все сообщения чата, отсортированные по времени создания"""
        result = await self.db.execute(
            select(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
        )
        return result.scalars().all()

    async def get_messages_by_ids(self, ids: List[str]) -> List[Message]:
        """Получает сообщения по списку ID"""
        result = await self.db.execute(select(Message).filter(Message.id.in_(ids)))
        return result.scalars().all()

    async def update_message(self, message: Message, **kwargs) -> Message:
        """Обновляет сообщение"""
        for key, value in kwargs.items():
            setattr(message, key, value)
        await self.db.commit()
        await self.db.refresh(message)
        return message
