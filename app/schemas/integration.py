import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


# Базовые схемы для устранения дублирования
class BaseIntegration(BaseModel):
    """Базовая схема для всех интеграций"""

    id: uuid.UUID
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BaseIntegrationCreate(BaseModel):
    """Базовая схема для создания интеграций"""

    is_active: bool = True


class BaseIntegrationUpdate(BaseModel):
    """Базовая схема для обновления интеграций"""

    is_active: Optional[bool] = None


# Схемы для Яндекс.Метрики
class YandexMetrikaIntegrationBase(BaseIntegrationCreate):
    """Базовая схема для Яндекс.Метрики"""

    counter_id: int
    token: str


class YandexMetrikaIntegrationUpdate(BaseIntegrationUpdate):
    """Схема для обновления Яндекс.Метрики"""

    counter_id: Optional[int] = None
    token: Optional[str] = None


class YandexMetrikaIntegration(BaseIntegration):
    """Полная схема интеграции Яндекс.Метрики"""

    counter_id: int
    token: str  # В ответах будет замаскирован
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class YandexMetrikaIntegrationResponse(BaseIntegration):
    """Безопасный ответ с интеграцией (без полного токена)"""

    counter_id: int
    has_token: bool
    token_preview: Optional[str] = None
    goals: Optional[list] = None
    data: Optional[list] = None


# Схемы для Google Analytics 4
class GoogleAnalyticsIntegrationBase(BaseIntegrationCreate):
    property_id: str


class GoogleAnalyticsIntegration(BaseIntegration):
    property_id: str

    class Config:
        from_attributes = True


class GoogleAnalyticsIntegrationResponse(BaseIntegration):
    property_id: str
    data: Optional[list] = None


# Общие схемы для списков интеграций
class IntegrationsListResponse(BaseModel):
    """Список подключенных интеграций компании"""

    integrations: List[str] = Field(
        default_factory=list
    )  # Массив slug-ов подключенных интеграций


# Универсальные запросы для операций
class ConnectIntegrationRequest(BaseModel):
    """Универсальный запрос на подключение интеграции"""

    # Данные для Яндекс.Метрики (добавляются если slug = "yandex-metrika")
    counter_id: Optional[int] = None
    token: Optional[str] = None

    # Данные для Google Analytics (если slug = "google-analytics")
    property_id: Optional[str] = None


class SyncIntegrationRequest(BaseModel):
    """Запрос на синхронизацию интеграции"""

    force: bool = Field(default=False, description="Принудительная синхронизация")


class IntegrationOperationResponse(BaseModel):
    """Универсальный ответ на операции с интеграциями"""

    success: bool
    message: str
    integration_type: str
    integration_id: Optional[uuid.UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[dict] = None


class YandexMetrikaGoal(BaseModel):
    """Схема для цели Яндекс.Метрики"""

    id: int
    name: str
