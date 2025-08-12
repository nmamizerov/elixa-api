import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    role: str
    content: str
    parent_id: Optional[uuid.UUID] = None
    path: List[str] = Field(default_factory=list)


class MessageRequest(BaseModel):
    chat_id: uuid.UUID
    role: str
    content: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None


class Message(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    role: str
    content: str
    parent_id: Optional[uuid.UUID] = None
    path: List[str]
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatCreate(BaseModel):
    title: str
    report_id: Optional[uuid.UUID] = None


class Chat(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    report_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class StreamEvent(BaseModel):
    """Базовая схема для стриминг событий"""

    type: Literal[
        "start", "thinking", "tool_start", "tool_result", "step", "final", "error"
    ]
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class StartEvent(StreamEvent):
    """Событие начала обработки"""

    type: Literal["start"] = "start"
    message: str


class ThinkingEvent(StreamEvent):
    """Событие размышления агента"""

    type: Literal["thinking"] = "thinking"
    message: str


class ToolStartEvent(StreamEvent):
    """Событие начала использования инструмента"""

    type: Literal["tool_start"] = "tool_start"
    tool_name: str
    message: str


class ToolResultEvent(StreamEvent):
    """Событие получения результата от инструмента"""

    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    message: str
    result: Optional[Dict[str, Any]] = None


class StepEvent(StreamEvent):
    """Событие промежуточного ответа агента"""

    type: Literal["step"] = "step"
    content: str


class FinalEvent(StreamEvent):
    """Событие финального ответа"""

    type: Literal["final"] = "final"
    content: str


class ErrorEvent(StreamEvent):
    """Событие ошибки"""

    type: Literal["error"] = "error"
    message: str


class StreamingMessageRequest(BaseModel):
    """Запрос для стриминга сообщения"""

    chat_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
