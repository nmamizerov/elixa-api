from typing import AsyncGenerator
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.config import SessionLocal

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.database.repositories import user_repository
from app.database.repositories.company_repository import CompanyRepository
from app.database.repositories.chat_repository import ChatRepository
from app.database.repositories.message_repository import MessageRepository
from app.database.repositories.report_repository import ReportRepository
from app.database.repositories.integration_repository import IntegrationRepository
from app.schemas.company import Company
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.services.report_service import ReportService
from app.services.conclusion_service import ConclusionService
from app.services.background_tasks import BackgroundTaskService, background_task_service
from app.services.s3_service import S3Service, s3_service
from app.core.config import settings
from app.database.models import user as user_model
from app.schemas import token as token_schema
from app.services.integrations_service import IntegrationsService
from app.services.integrations.yandex_metrika import YandexMetrikaService
from app.services.company_service import CompanyService
from app.schemas.integration import YandexMetrikaIntegration, GoogleAnalyticsIntegration

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> user_model.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = token_schema.TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user_repo = user_repository.UserRepository(db)
    user = await user_repo.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_from_query(
    db: AsyncSession = Depends(get_db), token: str = Query(...)
) -> user_model.User:
    """Получение текущего пользователя по токену из query параметров"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = token_schema.TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user_repo = user_repository.UserRepository(db)
    user = await user_repo.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


# Repository Dependencies
def get_company_repository(db: AsyncSession = Depends(get_db)) -> CompanyRepository:
    return CompanyRepository(db)


def get_chat_repository(db: AsyncSession = Depends(get_db)) -> ChatRepository:
    return ChatRepository(db)


def get_message_repository(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)


def get_report_repository(db: AsyncSession = Depends(get_db)) -> ReportRepository:
    return ReportRepository(db)


def get_integration_repository(
    db: AsyncSession = Depends(get_db),
) -> IntegrationRepository:
    return IntegrationRepository(db)


def get_yandex_metrika_service(
    integration_repo: IntegrationRepository = Depends(get_integration_repository),
) -> YandexMetrikaService:
    return YandexMetrikaService(integration_repo)


async def get_integrations_service(
    integration_repo: IntegrationRepository = Depends(get_integration_repository),
    yandex_metrika_service: YandexMetrikaService = Depends(get_yandex_metrika_service),
) -> IntegrationsService:
    """Получение сервиса интеграций"""
    return IntegrationsService(integration_repo, yandex_metrika_service)


def get_company_service(
    company_repo: CompanyRepository = Depends(get_company_repository),
) -> CompanyService:
    """Получение сервиса компаний"""
    return CompanyService(company_repo)


# Service Dependencies
def get_chat_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> ChatService:
    return ChatService(chat_repo)


def get_message_service(
    message_repo: MessageRepository = Depends(get_message_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    company_repo: CompanyRepository = Depends(get_company_repository),
    integration_repo: IntegrationRepository = Depends(get_integration_repository),
) -> MessageService:
    return MessageService(message_repo, chat_repo, company_repo, integration_repo)


def get_conclusion_service(
    report_repo: ReportRepository = Depends(get_report_repository),
) -> ConclusionService:
    return ConclusionService(report_repo)


def get_background_task_service() -> BackgroundTaskService:
    return background_task_service


def get_s3_service() -> S3Service:
    return s3_service


async def get_current_company(
    current_user: user_model.User = Depends(get_current_user),
    company_repo: CompanyRepository = Depends(get_company_repository),
) -> "Company":
    """Получение текущей компании для текущего пользователя"""
    from app.database.models.company import Company

    company = await company_repo.get_current_company(current_user.id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Компания не найдена. Убедитесь, что у вас есть доступ к компании.",
        )
    return company


async def get_yandex_metrika_integration(
    current_company: "Company" = Depends(get_current_company),
    integration_repo: IntegrationRepository = Depends(get_integration_repository),
) -> YandexMetrikaIntegration:
    integration = await integration_repo.get_yandex_metrika_integration_by_company_id(
        current_company.id
    )
    return integration


async def get_google_analytics_integration(
    current_company: "Company" = Depends(get_current_company),
    integration_repo: IntegrationRepository = Depends(get_integration_repository),
) -> GoogleAnalyticsIntegration | None:
    return await integration_repo.get_google_analytics_integration_by_company_id(
        current_company.id
    )


def get_report_service(
    report_repo: ReportRepository = Depends(get_report_repository),
    yandex_metrika_integration: YandexMetrikaIntegration | None = Depends(
        get_yandex_metrika_integration
    ),
    google_analytics_integration: GoogleAnalyticsIntegration | None = Depends(
        get_google_analytics_integration
    ),
) -> ReportService:
    return ReportService(
        report_repo,
        yandex_metrika_integration=yandex_metrika_integration,
        google_analytics_integration=google_analytics_integration,
    )


async def get_current_company_id(
    current_company: "Company" = Depends(get_current_company),
) -> uuid.UUID:
    """Получение ID текущей компании"""
    return current_company.id


async def get_user_companies(
    current_user: user_model.User = Depends(get_current_user),
    company_repo: CompanyRepository = Depends(get_company_repository),
) -> list["Company"]:
    """Dependency для получения списка компаний пользователя"""
    from app.database.models.company import Company

    companies = await company_repo.get_companies_by_user_id(current_user.id)
    return companies
