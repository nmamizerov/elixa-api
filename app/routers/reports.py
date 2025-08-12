import uuid
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from typing import Literal

from app.database.models.integration import YandexMetrikaIntegration
from app.database.models.user import User
from app.database.models.company import Company
from app.dependencies import (
    get_current_user,
    get_company_repository,
    get_report_service,
    get_conclusion_service,
    get_s3_service,
    get_current_company,
    get_user_companies,
    get_yandex_metrika_integration,
    get_google_analytics_integration,
)
from app.database.repositories.company_repository import CompanyRepository
from app.services.report_service import ReportService
from app.services.conclusion_service import ConclusionService
from app.services.background_tasks import background_task_service
from app.services.s3_service import S3Service

from app.schemas.report import (
    ReportResponse,
    ReportDeleteResponse,
    NewReportRequest,
    NewReportCreate,
    ReportCreateResponse,
    ReportDownloadResponse,
    ConclusionGenerateResponse,
    ConclusionStatusResponse,
    ConclusionRetryResponse,
    CompareReportRequest,
    CompareReportResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/", response_model=ReportCreateResponse)
async def create_new_report(
    report_data: NewReportRequest,
    current_company: Company = Depends(get_current_company),
    report_service: ReportService = Depends(get_report_service),
    yandex_metrika_integration: YandexMetrikaIntegration | None = Depends(
        get_yandex_metrika_integration
    ),
    google_analytics_integration=Depends(get_google_analytics_integration),
):
    """Создание нового отчета с фоновой обработкой (providers + traffic_kind)."""

    # Создаем объект для создания отчета
    new_report_create = NewReportCreate(
        company_id=current_company.id, request_data=report_data
    )

    # Создаем отчет в базе со статусом "proceed"
    report = await report_service.create_new_report(new_report_create, current_company)

    # Строим список источников из providers + traffic_kind
    sources_list = [
        {"provider": p, "traffic_kind": report_data.traffic_kind}
        for p in (report_data.providers or [])
    ]

    # Определяем какие интеграции реально нужны
    use_yandex = (
        yandex_metrika_integration
        if "yandex_metrika" in report_data.providers
        else None
    )
    use_google = (
        google_analytics_integration
        if "google_analytics" in report_data.providers
        else None
    )

    # Запускаем фоновую задачу для генерации отчета строго по переданным источникам
    background_task_service.start_report_generation(
        report.id, use_yandex, use_google, sources_list
    )  # type: ignore

    return ReportCreateResponse(
        id=report.id,
        status=report.status.value,
        message="Report created and queued for processing",
    )


@router.get("/", response_model=List[ReportResponse])
async def get_user_reports(
    limit: int = 50,
    current_company: Company = Depends(get_current_company),
    report_service: ReportService = Depends(get_report_service),
):
    """Получение отчетов пользователя"""

    reports = await report_service.get_reports_by_company(current_company.id, limit)
    # Для списка отчетов не генерируем превью данных (with_data_preview=False по умолчанию)
    response_tasks = [report_service.to_response(report) for report in reports]
    return await asyncio.gather(*response_tasks)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    user_companies: list[Company] = Depends(get_user_companies),
    report_service: ReportService = Depends(get_report_service),
):
    """Получение отчета по ID"""

    # Получаем отчет
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Проверяем доступ пользователя к отчету
    user_company_ids = [company.id for company in user_companies]

    if report.company_id not in user_company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    return await report_service.to_response(report, with_data_preview=True)


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
async def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_repo: CompanyRepository = Depends(get_company_repository),
    report_service: ReportService = Depends(get_report_service),
):
    """Удаление отчета"""

    # Получаем отчет
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Проверяем доступ пользователя к отчету
    user_companies = await company_repo.get_companies_by_user_id(current_user.id)
    user_company_ids = [company.id for company in user_companies]

    if report.company_id not in user_company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    success = await report_service.delete_report(report_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete report",
        )

    return ReportDeleteResponse()


@router.post("/{report_id}/retry", response_model=ReportCreateResponse)
async def retry_report_generation(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_repo: CompanyRepository = Depends(get_company_repository),
    report_service: ReportService = Depends(get_report_service),
    yandex_metrika_integration: YandexMetrikaIntegration = Depends(
        get_yandex_metrika_integration
    ),
):
    """Повторная генерация отчета в случае ошибки"""

    # Получаем отчет
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Проверяем доступ пользователя к отчету
    user_companies = await company_repo.get_companies_by_user_id(current_user.id)
    user_company_ids = [company.id for company in user_companies]

    if report.company_id not in user_company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    # Проверяем что отчет имеет статус failed
    if report.status.value != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed reports can be retried",
        )

    # Обновляем статус отчета на proceed и очищаем file_name
    success = await report_service.retry_report_generation(report_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry report generation",
        )

    # Запускаем фоновую задачу для генерации отчета
    background_task_service.start_report_generation(
        report_id, yandex_metrika_integration
    )

    # Возвращаем ответ с информацией об отчете
    return ReportCreateResponse(
        id=report_id,
        status="proceed",
        message="Report retry started and queued for processing",
    )


@router.get("/{report_id}/download", response_model=ReportDownloadResponse)
async def get_report_download_url(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    company_repo: CompanyRepository = Depends(get_company_repository),
    report_service: ReportService = Depends(get_report_service),
    s3_service: S3Service = Depends(get_s3_service),
):
    """Получение ссылки для скачивания отчета"""

    # Получаем отчет
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Проверяем доступ пользователя к отчету
    user_companies = await company_repo.get_companies_by_user_id(current_user.id)
    user_company_ids = [company.id for company in user_companies]

    if report.company_id not in user_company_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    # Проверяем что отчет готов для скачивания
    if report.status.value != "finish" or not report.file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )

    # Получаем ссылку для скачивания из S3
    download_url = await s3_service.get_report_download_url(report.file_name)
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        )

    return ReportDownloadResponse(
        download_url=download_url, expires_in=3600, file_name=report.file_name
    )


@router.post("/{report_id}/conclusion", response_model=ConclusionGenerateResponse)
async def generate_report_conclusion(
    report_id: uuid.UUID,
    current_company: Company = Depends(get_current_company),
    report_service: ReportService = Depends(get_report_service),
):
    """Генерация заключения для отчета"""

    # Проверяем, что отчет принадлежит компании пользователя
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    if report.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    # Проверяем, что отчет готов
    if report.status.value != "finish" or not report.file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for conclusion generation",
        )

    # Запускаем генерацию заключения в фоновом режиме
    background_task_service.start_conclusion_generation(report_id)

    return ConclusionGenerateResponse(
        message="Conclusion generation started", report_id=report_id, status="proceed"
    )


@router.get("/{report_id}/conclusion/status", response_model=ConclusionStatusResponse)
async def get_conclusion_status(
    report_id: uuid.UUID,
    current_company: Company = Depends(get_current_company),
    report_service: ReportService = Depends(get_report_service),
):
    """Получение статуса генерации заключения"""

    # Проверяем, что отчет принадлежит компании пользователя
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    if report.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    return ConclusionStatusResponse(
        report_id=report_id,
        conclusion_status=(
            report.conclusion_status.value if report.conclusion_status else "waiting"
        ),
        conclusion=report.conclusion,
        user_waiting_for_conclusion=report.user_waiting_for_conclusion,
    )


@router.post("/{report_id}/conclusion/retry", response_model=ConclusionRetryResponse)
async def retry_conclusion_generation(
    report_id: uuid.UUID,
    current_company: Company = Depends(get_current_company),
    report_service: ReportService = Depends(get_report_service),
):
    """Повторная генерация заключения"""

    # Проверяем, что отчет принадлежит компании пользователя
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    if report.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    # Проверяем, что отчет готов
    if report.status.value != "finish" or not report.file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for conclusion generation",
        )

    # Запускаем повторную генерацию заключения
    background_task_service.start_conclusion_generation(report_id)

    return ConclusionRetryResponse(
        message="Conclusion generation restarted", report_id=report_id, status="proceed"
    )


@router.post("/{report_id}/compare", response_model=CompareReportResponse)
async def create_compare_report(
    report_id: uuid.UUID,
    compare_data: CompareReportRequest,
    current_company: Company = Depends(get_current_company),
    yandex_metrika_integration: YandexMetrikaIntegration = Depends(
        get_yandex_metrika_integration
    ),
    report_service: ReportService = Depends(get_report_service),
):
    """Создание отчета сравнения на основе существующего отчета"""

    # Проверяем, что исходный отчет существует и принадлежит компании
    original_report = await report_service.get_report_by_id(report_id)
    if not original_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Original report not found"
        )

    if original_report.company_id != current_company.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this report"
        )

    try:
        # Создаем или находим существующий отчет сравнения
        compare_report, is_existing = await report_service.create_compare_report(
            report_id, compare_data.date_1, compare_data.date_2
        )

        # Если отчет новый, запускаем генерацию
        if not is_existing:
            background_task_service.start_report_generation(
                compare_report.id, yandex_metrika_integration
            )
            message = "Comparison report created and queued for processing"
        else:
            message = "Existing comparison report found"

        return CompareReportResponse(
            report_id=compare_report.id,
            message=message,
            is_existing=is_existing,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating comparison report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comparison report",
        )
