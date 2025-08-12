import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status

from app.database.models.user import User
from app.dependencies import (
    get_current_user,
    get_company_service,
    get_integrations_service,
)
from app.services.company_service import CompanyService
from app.schemas.company import (
    Company,
    CompanyUpdate,
    CompanyUserResponse,
    AddUserToCompanyRequest,
    UpdateUserRoleRequest,
    CompanyListResponse,
    CompanyDetailResponse,
    SetCurrentCompanyRequest,
)
from app.services.integrations_service import IntegrationsService
from app.schemas.integration import YandexMetrikaGoal

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=List[CompanyListResponse])
async def get_my_companies(
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Получение списка компаний пользователя"""
    companies_data = await company_service.get_user_companies(current_user.id)

    result = []
    for data in companies_data:
        result.append(
            CompanyListResponse(
                id=data["company"].id,
                name=data["company"].name,
                my_role=data["role"].value,
                is_current=data["is_current"],
                user_count=data["user_count"],
            )
        )

    return result


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company_detail(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Получение детальной информации о компании"""
    company_data = await company_service.get_company_detail(company_id, current_user.id)

    if not company_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Компания не найдена или у вас нет доступа к ней",
        )

    company = company_data["company"]

    return CompanyDetailResponse(
        id=company.id,
        name=company.name,
        expires_at=company.expires_at,
        created_at=company.created_at,
        my_role=company_data["role"].value,
        is_current=company_data["is_current"],
        user_count=company_data["user_count"],
    )


@router.put("/{company_id}", response_model=CompanyDetailResponse)
async def update_company(
    company_id: uuid.UUID,
    company_update: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Обновление компании (только для владельца)"""
    result = await company_service.update_company(
        company_id, current_user.id, company_update
    )

    updated_company = result["company"]
    company_data = result["company_data"]

    return CompanyDetailResponse(
        id=updated_company.id,
        name=updated_company.name,
        ym_counter=updated_company.ym_counter,
        ym_token=updated_company.ym_token,
        expires_at=updated_company.expires_at,
        created_at=updated_company.created_at,
        my_role=company_data["role"].value,
        is_current=company_data["is_current"],
        user_count=company_data["user_count"],
    )


@router.post("/set-current")
async def set_current_company(
    request: SetCurrentCompanyRequest,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Установка текущей компании для пользователя"""
    success = await company_service.set_current_company(
        current_user.id, request.company_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось установить текущую компанию. Проверьте доступ к компании.",
        )

    return {"message": "Текущая компания успешно установлена"}


@router.get("/{company_id}/users", response_model=List[CompanyUserResponse])
async def get_company_users(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Получение списка пользователей компании"""
    company_users_data = await company_service.get_company_users(
        company_id, current_user.id
    )

    result = []
    for user_data in company_users_data:
        result.append(
            CompanyUserResponse(
                id=user_data["id"],
                user_id=user_data["user_id"],
                user_email=user_data["user_email"],
                role=user_data["role"],
                created_at=user_data["created_at"],
            )
        )

    return result


@router.post("/{company_id}/users", response_model=CompanyUserResponse)
async def add_user_to_company(
    company_id: uuid.UUID,
    request: AddUserToCompanyRequest,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Добавление пользователя в компанию"""
    company_user_data = await company_service.add_user_to_company(
        company_id, current_user.id, request
    )

    return CompanyUserResponse(
        id=company_user_data["id"],
        user_id=company_user_data["user_id"],
        user_email=company_user_data["user_email"],
        role=company_user_data["role"],
        created_at=company_user_data["created_at"],
    )


@router.put("/{company_id}/users/{user_id}/role", response_model=CompanyUserResponse)
async def update_user_role(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    request: UpdateUserRoleRequest,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Изменение роли пользователя в компании"""
    company_user_data = await company_service.update_user_role(
        company_id, current_user.id, user_id, request
    )

    return CompanyUserResponse(
        id=company_user_data["id"],
        user_id=company_user_data["user_id"],
        user_email=company_user_data["user_email"],
        role=company_user_data["role"],
        created_at=company_user_data["created_at"],
    )


@router.delete("/{company_id}/users/{user_id}")
async def remove_user_from_company(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_service: CompanyService = Depends(get_company_service),
):
    """Удаление пользователя из компании"""
    await company_service.remove_user_from_company(company_id, current_user.id, user_id)

    return {"message": "Пользователь успешно удален из компании"}


@router.get("/{company_id}/goals")
async def get_company_goals(
    company_id: uuid.UUID,
    integrations_service: IntegrationsService = Depends(get_integrations_service),
) -> List[YandexMetrikaGoal]:
    """Получение целей компании"""
    yandex_metrika_integration = (
        await integrations_service.get_yandex_metrika_integration_detail(company_id)
    )
    return yandex_metrika_integration.goals
