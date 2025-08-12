import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from app.dependencies import (
    get_current_company_id,
    get_integrations_service,
)
from app.services.integrations_service import IntegrationsService
from app.schemas.integration import (
    ConnectIntegrationRequest,
    SyncIntegrationRequest,
    IntegrationOperationResponse,
    IntegrationsListResponse,
    YandexMetrikaIntegrationBase,
    YandexMetrikaIntegrationResponse,
    GoogleAnalyticsIntegrationBase,
    GoogleAnalyticsIntegrationResponse,
)


router = APIRouter(prefix="/integrations", tags=["integrations"])


def validate_integration_slug(slug: str) -> str:
    """Валидация slug интеграции"""
    supported_slugs = ["yandex-metrika", "google-analytics"]

    if slug not in supported_slugs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый тип интеграции: {slug}. Поддерживаются: {', '.join(supported_slugs)}",
        )

    return slug


@router.get("/", response_model=IntegrationsListResponse)
async def get_integrations(
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
):
    """Получение списка всех интеграций компании"""
    try:
        return await integrations_service.get_company_integrations(company_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения интеграций: {str(e)}",
        )


@router.get("/yandex-metrika", response_model=YandexMetrikaIntegrationResponse)
async def get_yandex_metrika_integration(
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
):
    """Получение интеграции Яндекс.Метрики"""
    try:
        return await integrations_service.get_yandex_metrika_integration_detail(
            company_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения интеграций: {str(e)}",
        )


@router.get("/google-analytics", response_model=GoogleAnalyticsIntegrationResponse)
async def get_google_analytics_integration(
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
):
    """Получение интеграции Google Analytics 4"""
    try:
        return await integrations_service.get_google_analytics_integration_detail(
            company_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения интеграций: {str(e)}",
        )


@router.post("/{slug}", response_model=IntegrationOperationResponse)
async def connect_integration(
    slug: str,
    request: ConnectIntegrationRequest,
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
):
    """Подключение интеграции"""
    validated_slug = validate_integration_slug(slug)

    try:
        if validated_slug == "yandex-metrika":
            # Валидируем обязательные поля для Яндекс.Метрики
            if not all([request.counter_id, request.token]):
                raise ValueError(
                    "Для Яндекс.Метрики обязательны поля: name, counter_id, token"
                )

            ym_request = YandexMetrikaIntegrationBase(
                counter_id=request.counter_id,
                token=request.token,
            )

            integration = await integrations_service.connect_yandex_metrika(
                company_id, ym_request
            )

            return IntegrationOperationResponse(
                success=True,
                message="Интеграция с Яндекс.Метрикой успешно подключена",
                integration_type="yandex-metrika",
                integration_id=integration.id,
                timestamp=datetime.now(),
                details={
                    "counter_id": integration.counter_id,
                    "is_active": integration.is_active,
                },
            )

        elif validated_slug == "google-analytics":
            if not request.property_id:
                raise ValueError(
                    "Для Google Analytics обязательное поле: property_id (GA4 Property ID)"
                )

            ga_request = GoogleAnalyticsIntegrationBase(property_id=request.property_id)
            integration = await integrations_service.connect_google_analytics(
                company_id, ga_request
            )

            return IntegrationOperationResponse(
                success=True,
                message="Интеграция с Google Analytics 4 успешно подключена",
                integration_type="google-analytics",
                integration_id=integration.id,
                timestamp=datetime.now(),
                details={
                    "property_id": integration.property_id,
                    "is_active": integration.is_active,
                },
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Подключение интеграции {slug} пока не реализовано",
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подключения интеграции: {str(e)}",
        )


@router.put("/{slug}")
async def sync_integration(
    slug: str,
    request: SyncIntegrationRequest = SyncIntegrationRequest(),
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
) -> bool:
    """Синхронизация интеграции"""
    if slug == "yandex-metrika":
        return await integrations_service.sync_yandex_metrika_integration(company_id)
    elif slug == "google-analytics":
        # Пока no-op, синхронизация GA4 метаданных будет добавлена позже
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Синхронизация интеграции {slug} пока не реализована",
        )


@router.delete("/{slug}", response_model=IntegrationOperationResponse)
async def disconnect_integration(
    slug: str,
    company_id: uuid.UUID = Depends(get_current_company_id),
    integrations_service: IntegrationsService = Depends(get_integrations_service),
):
    """Отключение интеграции"""
    validated_slug = validate_integration_slug(slug)

    try:
        if validated_slug == "yandex-metrika":
            ym_integration = (
                await integrations_service.get_yandex_metrika_integration_detail(
                    company_id
                )
            )
            if not ym_integration:
                raise ValueError("Активная интеграция с Яндекс.Метрикой не найдена")
            success = await integrations_service.disconnect_yandex_metrika_integration(
                ym_integration.id, company_id
            )

            if not success:
                raise ValueError("Не удалось отключить интеграцию")

            return IntegrationOperationResponse(
                success=True,
                message="Интеграция с Яндекс.Метрикой успешно отключена",
                integration_type="yandex-metrika",
                integration_id=ym_integration.id,
                timestamp=datetime.now(),
                details={"counter_id": ym_integration.counter_id},
            )

        elif validated_slug == "google-analytics":
            integration = (
                await integrations_service.get_google_analytics_integration_detail(
                    company_id
                )
            )
            if not integration:
                raise ValueError("Активная интеграция с Google Analytics не найдена")
            success = (
                await integrations_service.disconnect_google_analytics_integration(
                    integration.id, company_id
                )
            )
            if not success:
                raise ValueError("Не удалось отключить интеграцию")
            return IntegrationOperationResponse(
                success=True,
                message="Интеграция с Google Analytics 4 успешно отключена",
                integration_type="google-analytics",
                integration_id=integration.id,
                timestamp=datetime.now(),
                details={"property_id": integration.property_id},
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Отключение интеграции {slug} пока не реализовано",
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отключения интеграции: {str(e)}",
        )
