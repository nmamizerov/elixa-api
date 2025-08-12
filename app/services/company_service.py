import uuid
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from app.database.repositories.company_repository import CompanyRepository
from app.database.models.company import CompanyUserRole
from app.database.models.user import User
from app.schemas.company import (
    CompanyUpdate,
    AddUserToCompanyRequest,
    UpdateUserRoleRequest,
    SetCurrentCompanyRequest,
)


class CompanyService:
    def __init__(self, company_repository: CompanyRepository):
        self.company_repo = company_repository

    async def get_user_companies(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Получение списка компаний пользователя с ролями"""
        return await self.company_repo.get_user_companies_with_roles(user_id)

    async def get_company_detail(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Получение детальной информации о компании"""
        return await self.company_repo.get_company_with_user_role(company_id, user_id)

    async def check_company_owner_access(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> None:
        """Проверка прав владельца компании"""
        is_owner = await self.company_repo.is_company_owner(user_id, company_id)
        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав. Требуются права владельца компании.",
            )

    async def update_company(
        self, company_id: uuid.UUID, user_id: uuid.UUID, company_update: CompanyUpdate
    ) -> Optional[Dict[str, Any]]:
        """Обновление компании (только для владельца)"""
        # Проверяем права владельца
        await self.check_company_owner_access(user_id, company_id)

        # Подготавливаем данные для обновления
        update_data = {}
        if company_update.name is not None:
            update_data["name"] = company_update.name
        if company_update.ym_counter is not None:
            update_data["ym_counter"] = company_update.ym_counter
        if company_update.ym_token is not None:
            update_data["ym_token"] = company_update.ym_token
        if company_update.expires_at is not None:
            update_data["expires_at"] = company_update.expires_at

        # Обновляем компанию
        updated_company = await self.company_repo.update_company_by_owner(
            company_id, user_id, update_data
        )

        if not updated_company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Компания не найдена"
            )

        # Получаем обновленную информацию с ролью
        company_data = await self.company_repo.get_company_with_user_role(
            company_id, user_id
        )

        return {"company": updated_company, "company_data": company_data}

    async def set_current_company(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        """Установка текущей компании для пользователя"""
        return await self.company_repo.set_current_company(user_id, company_id)

    async def get_company_users(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """Получение списка пользователей компании"""
        # Проверяем доступ к компании
        company_data = await self.company_repo.get_company_with_user_role(
            company_id, user_id
        )
        if not company_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена или у вас нет доступа к ней",
            )

        # Получаем всех пользователей компании
        company_users = await self.company_repo.get_company_users(company_id)

        # Формируем результат с информацией о пользователях
        result = []
        for cu in company_users:
            # Загружаем связанные данные пользователя
            await self.company_repo.db.refresh(cu, ["user"])
            result.append(
                {
                    "id": cu.id,
                    "user_id": cu.user_id,
                    "user_email": cu.user.email,
                    "role": cu.role.value,
                    "created_at": cu.created_at,
                }
            )

        return result

    async def add_user_to_company(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AddUserToCompanyRequest,
    ) -> Dict[str, Any]:
        """Добавление пользователя в компанию"""
        # Проверяем права владельца
        await self.check_company_owner_access(user_id, company_id)

        # Находим пользователя по email
        user_to_add = await self.company_repo.get_user_by_email(request.user_email)
        if not user_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с email {request.user_email} не найден",
            )

        # Проверяем роль
        if request.role not in ["owner", "member"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Роль должна быть 'owner' или 'member'",
            )

        role = (
            CompanyUserRole.owner if request.role == "owner" else CompanyUserRole.member
        )

        try:
            # Добавляем пользователя в компанию
            company_user = await self.company_repo.add_user_to_company(
                company_id, user_to_add.id, role
            )

            # Загружаем связанные данные
            await self.company_repo.db.refresh(company_user, ["user"])

            return {
                "id": company_user.id,
                "user_id": company_user.user_id,
                "user_email": company_user.user.email,
                "role": company_user.role.value,
                "created_at": company_user.created_at,
            }
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def update_user_role(
        self,
        company_id: uuid.UUID,
        owner_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateUserRoleRequest,
    ) -> Dict[str, Any]:
        """Изменение роли пользователя в компании"""
        # Проверяем права владельца
        await self.check_company_owner_access(owner_id, company_id)

        # Проверяем роль
        if request.role not in ["owner", "member"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Роль должна быть 'owner' или 'member'",
            )

        new_role = (
            CompanyUserRole.owner if request.role == "owner" else CompanyUserRole.member
        )

        try:
            # Обновляем роль пользователя
            company_user = await self.company_repo.update_user_role(
                company_id, user_id, new_role
            )

            if not company_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден в компании",
                )

            # Загружаем связанные данные
            await self.company_repo.db.refresh(company_user, ["user"])

            return {
                "id": company_user.id,
                "user_id": company_user.user_id,
                "user_email": company_user.user.email,
                "role": company_user.role.value,
                "created_at": company_user.created_at,
            }
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def remove_user_from_company(
        self, company_id: uuid.UUID, owner_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Удаление пользователя из компании"""
        # Проверяем права владельца
        await self.check_company_owner_access(owner_id, company_id)

        try:
            # Удаляем пользователя из компании
            success = await self.company_repo.remove_user_from_company(
                company_id, user_id
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден в компании",
                )

            return success
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def get_company_goals(self, company_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Получение целей компании"""
        yandex_metrika_goals = await self.company_repo.get_yandex_metrika_goals(
            company_id
        )
        return yandex_metrika_goals
