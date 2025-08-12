import uuid
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: uuid.UUID
    current_company_id: uuid.UUID | None = None

    class Config:
        from_attributes = True


class UserRegistrationResponse(BaseModel):
    """Ответ при регистрации пользователя"""

    user: User
    company_created: bool = True
    message: str = (
        "Пользователь успешно зарегистрирован. Компания создана автоматически."
    )
    setup_required: str = (
        "Необходимо настроить интеграцию с Яндекс.Метрикой в разделе 'Компании'"
    )
