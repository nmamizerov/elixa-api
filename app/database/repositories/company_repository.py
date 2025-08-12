import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List

from app.database.models.company import Company, CompanyUser, CompanyUserRole
from app.database.models.user import User
from app.schemas.company import CompanyCreate, CompanyUserCreate


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_first_company_by_user_id(
        self, user_id: uuid.UUID
    ) -> Optional[Company]:
        """Получает первую компанию пользователя (с учетом новой системы ролей)"""
        # Сначала пробуем найти через старую связь (для обратной совместимости)
        stmt = select(Company).where(Company.user_id == user_id).limit(1)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if company:
            return company

        # Если не найдено через старую связь, ищем через CompanyUser
        stmt = (
            select(Company)
            .join(CompanyUser)
            .where(CompanyUser.user_id == user_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_companies_by_user_id(self, user_id: uuid.UUID) -> list[Company]:
        """Получает все компании пользователя (с учетом новой системы ролей)"""
        # Получаем компании через старую связь и через CompanyUser
        stmt1 = select(Company).where(Company.user_id == user_id)
        result1 = await self.db.execute(stmt1)
        companies_old = list(result1.scalars().all())

        stmt2 = select(Company).join(CompanyUser).where(CompanyUser.user_id == user_id)
        result2 = await self.db.execute(stmt2)
        companies_new = list(result2.scalars().all())

        # Объединяем и убираем дубликаты
        all_companies = {c.id: c for c in companies_old + companies_new}
        return list(all_companies.values())

    async def create_company(
        self, user_id: uuid.UUID, company_data: CompanyCreate
    ) -> Company:
        """Создает новую компанию для пользователя"""
        db_company = Company(
            user_id=user_id,
            name=company_data.name,
            expires_at=company_data.expires_at,
        )
        self.db.add(db_company)
        await self.db.commit()
        await self.db.refresh(db_company)

        # Автоматически добавляем создателя как owner
        company_user = CompanyUser(
            user_id=user_id, company_id=db_company.id, role=CompanyUserRole.owner
        )
        self.db.add(company_user)
        await self.db.commit()

        return db_company

    # Методы для работы с пользователями компании

    async def get_user_role_in_company(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> Optional[CompanyUserRole]:
        """Получение роли пользователя в компании"""
        stmt = select(CompanyUser.role).where(
            and_(CompanyUser.user_id == user_id, CompanyUser.company_id == company_id)
        )
        result = await self.db.execute(stmt)
        role = result.scalar_one_or_none()
        return role

    async def is_company_owner(self, user_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        """Проверка, является ли пользователь владельцем компании"""
        role = await self.get_user_role_in_company(user_id, company_id)
        return role == CompanyUserRole.owner

    async def get_company_users(self, company_id: uuid.UUID) -> List[CompanyUser]:
        """Получение всех пользователей компании"""
        stmt = (
            select(CompanyUser)
            .where(CompanyUser.company_id == company_id)
            .join(User)
            .order_by(CompanyUser.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_user_to_company(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        role: CompanyUserRole = CompanyUserRole.member,
    ) -> CompanyUser:
        """Добавление пользователя в компанию"""
        # Проверяем, не добавлен ли уже пользователь
        existing = await self.db.execute(
            select(CompanyUser).where(
                and_(
                    CompanyUser.user_id == user_id, CompanyUser.company_id == company_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Пользователь уже добавлен в компанию")

        company_user = CompanyUser(user_id=user_id, company_id=company_id, role=role)
        self.db.add(company_user)
        await self.db.commit()
        await self.db.refresh(company_user)
        return company_user

    async def remove_user_from_company(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Удаление пользователя из компании"""
        stmt = select(CompanyUser).where(
            and_(CompanyUser.user_id == user_id, CompanyUser.company_id == company_id)
        )
        result = await self.db.execute(stmt)
        company_user = result.scalar_one_or_none()

        if not company_user:
            return False

        # Нельзя удалить последнего владельца
        if company_user.role == CompanyUserRole.owner:
            owners_count = await self.db.execute(
                select(CompanyUser).where(
                    and_(
                        CompanyUser.company_id == company_id,
                        CompanyUser.role == CompanyUserRole.owner,
                    )
                )
            )
            if len(list(owners_count.scalars().all())) <= 1:
                raise ValueError("Нельзя удалить последнего владельца компании")

        await self.db.delete(company_user)
        await self.db.commit()
        return True

    async def update_user_role(
        self, company_id: uuid.UUID, user_id: uuid.UUID, new_role: CompanyUserRole
    ) -> Optional[CompanyUser]:
        """Изменение роли пользователя в компании"""
        stmt = select(CompanyUser).where(
            and_(CompanyUser.user_id == user_id, CompanyUser.company_id == company_id)
        )
        result = await self.db.execute(stmt)
        company_user = result.scalar_one_or_none()

        if not company_user:
            return None

        # Проверяем, что не убираем последнего владельца
        if (
            company_user.role == CompanyUserRole.owner
            and new_role != CompanyUserRole.owner
        ):
            owners_count = await self.db.execute(
                select(CompanyUser).where(
                    and_(
                        CompanyUser.company_id == company_id,
                        CompanyUser.role == CompanyUserRole.owner,
                    )
                )
            )
            if len(list(owners_count.scalars().all())) <= 1:
                raise ValueError(
                    "Нельзя убрать права владельца у последнего владельца компании"
                )

        company_user.role = new_role
        await self.db.commit()
        await self.db.refresh(company_user)
        return company_user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Поиск пользователя по email"""
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_companies_with_roles(self, user_id: uuid.UUID) -> List[dict]:
        """Получение всех компаний пользователя с информацией о ролях"""
        # Получаем компании через CompanyUser
        stmt = (
            select(Company, CompanyUser.role, User.current_company_id)
            .join(CompanyUser, Company.id == CompanyUser.company_id)
            .join(User, User.id == CompanyUser.user_id)
            .where(CompanyUser.user_id == user_id)
            .order_by(Company.created_at)
        )
        result = await self.db.execute(stmt)
        companies_data = result.all()

        # Получаем количество пользователей для каждой компании
        companies_with_info = []
        for company, role, current_company_id in companies_data:
            # Подсчитываем количество пользователей в компании
            user_count_stmt = select(CompanyUser).where(
                CompanyUser.company_id == company.id
            )
            user_count_result = await self.db.execute(user_count_stmt)
            user_count = len(list(user_count_result.scalars().all()))

            companies_with_info.append(
                {
                    "company": company,
                    "role": role,
                    "is_current": company.id == current_company_id,
                    "user_count": user_count,
                }
            )

        return companies_with_info

    async def get_company_with_user_role(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[dict]:
        """Получение компании с информацией о роли пользователя"""
        # Проверяем доступ пользователя к компании
        stmt = (
            select(Company, CompanyUser.role, User.current_company_id)
            .join(CompanyUser, Company.id == CompanyUser.company_id)
            .join(User, User.id == CompanyUser.user_id)
            .where(and_(Company.id == company_id, CompanyUser.user_id == user_id))
        )
        result = await self.db.execute(stmt)
        data = result.first()

        if not data:
            return None

        company, role, current_company_id = data

        # Подсчитываем количество пользователей в компании
        user_count_stmt = select(CompanyUser).where(
            CompanyUser.company_id == company.id
        )
        user_count_result = await self.db.execute(user_count_stmt)
        user_count = len(list(user_count_result.scalars().all()))

        return {
            "company": company,
            "role": role,
            "is_current": company.id == current_company_id,
            "user_count": user_count,
        }

    async def set_current_company(
        self, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> bool:
        """Установка текущей компании для пользователя"""
        # Проверяем, что пользователь имеет доступ к компании
        role = await self.get_user_role_in_company(user_id, company_id)
        if not role:
            return False

        # Обновляем current_company_id
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.current_company_id = company_id
        await self.db.commit()
        return True

    async def update_company_by_owner(
        self, company_id: uuid.UUID, user_id: uuid.UUID, update_data: dict
    ) -> Optional[Company]:
        """Обновление компании (только для владельца)"""
        # Проверяем права владельца
        is_owner = await self.is_company_owner(user_id, company_id)
        if not is_owner:
            return None

        # Получаем компанию
        stmt = select(Company).where(Company.id == company_id)
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            return None

        # Обновляем поля
        for field, value in update_data.items():
            if hasattr(company, field) and value is not None:
                setattr(company, field, value)

        await self.db.commit()
        await self.db.refresh(company)
        return company

    async def get_current_company(self, user_id: uuid.UUID) -> Optional[Company]:
        """Получение текущей компании пользователя"""
        # Получаем пользователя с current_company_id
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.current_company_id:
            # Если current_company_id не установлен, пробуем получить первую доступную компанию
            return await self.get_first_company_by_user_id(user_id)

        # Проверяем, что у пользователя есть доступ к current_company
        company_data = await self.get_company_with_user_role(
            user.current_company_id, user_id
        )
        if company_data:
            return company_data["company"]

        return None

    async def create_default_company(
        self, user_id: uuid.UUID, user_email: str
    ) -> Company:
        """Создает компанию по умолчанию для нового пользователя"""
        # Создаем компанию с заглушечными данными
        default_name = f"Компания {user_email.split('@')[0]}"

        db_company = Company(
            user_id=user_id,
            name=default_name,
            expires_at=None,
        )
        self.db.add(db_company)
        await self.db.commit()
        await self.db.refresh(db_company)

        # Автоматически добавляем создателя как owner
        company_user = CompanyUser(
            user_id=user_id, company_id=db_company.id, role=CompanyUserRole.owner
        )
        self.db.add(company_user)
        await self.db.commit()

        return db_company
