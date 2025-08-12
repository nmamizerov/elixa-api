import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional


class CompanyBase(BaseModel):
    name: str


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    pass


class Company(CompanyBase):
    id: uuid.UUID
    user_id: uuid.UUID

    class Config:
        from_attributes = True


class CompanyUserBase(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str  # "owner" или "member"


class CompanyUserCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "member"


class CompanyUserUpdate(BaseModel):
    role: str


class CompanyUser(CompanyUserBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyUserResponse(BaseModel):
    """Ответ с информацией о пользователе компании"""

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    role: str
    created_at: datetime


class AddUserToCompanyRequest(BaseModel):
    """Запрос на добавление пользователя в компанию"""

    user_email: str
    role: str = "member"


class UpdateUserRoleRequest(BaseModel):
    """Запрос на изменение роли пользователя"""

    role: str


class CompanyListResponse(BaseModel):
    """Ответ со списком компаний пользователя"""

    id: uuid.UUID
    name: str
    my_role: str
    is_current: bool
    user_count: int = 0


class CompanyDetailResponse(BaseModel):
    """Детальная информация о компании"""

    id: uuid.UUID
    name: str
    created_at: datetime
    my_role: str
    is_current: bool
    user_count: int = 0


class SetCurrentCompanyRequest(BaseModel):
    """Запрос на установку текущей компании"""

    company_id: uuid.UUID
