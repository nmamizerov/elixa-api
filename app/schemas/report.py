from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class ReportState(BaseModel):
    """Состояние отчета для генерации"""

    attributes: List[str] = Field(default_factory=list)
    selected_goals: List[Dict[str, str]] = Field(default_factory=list)
    selected_metrics: List[str] = Field(default_factory=list)
    source: Literal["paid", "free", "all"] = "paid"
    date_1: str
    date_2: str
    additional_metrics: str = ""
    cpa_goal: Optional[str] = None
    cpo_goal: Optional[str] = None
    compare_date_1: Optional[str] = None
    compare_date_2: Optional[str] = None


class ReportData(BaseModel):
    """Данные отчета"""

    headers: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    meta_data: Optional[List[Any]] = Field(default_factory=list)


class MetrikaApiResponse(BaseModel):
    """Ответ от API Яндекс.Метрики"""

    data: List[Dict[str, Any]] = Field(default_factory=list)
    query: Optional[Dict[str, Any]] = None
    total_rows: Optional[int] = None
    sampled: Optional[bool] = None


class MetrikaApiRequest(BaseModel):
    """Запрос к API Яндекс.Метрики"""

    dimensions: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    date_1: str
    date_2: str
    filters: Optional[str] = None
    direct_client_logins: Optional[str] = None
    limit: int = 100
    offset: int = 1


class GoalMetric(BaseModel):
    """Метрика цели"""

    goal_id: int
    goal_name: str
    metric_name: str
    value: Optional[float] = None


class CalculatedMetrics(BaseModel):
    """Расчитанные метрики"""

    cpc: Optional[float] = None
    cr: Optional[float] = None
    cpo: Optional[float] = None
    cpa: Optional[float] = None
    cac: Optional[float] = None
    romi: Optional[float] = None
    drr: Optional[float] = None
    roi: Optional[float] = None


# Тип провайдера
ProviderSlug = Literal["yandex_metrika", "google_analytics"]


class ReportSource(BaseModel):
    provider: Literal["yandex_metrika", "google_analytics"] = "yandex_metrika"
    traffic_kind: Literal["paid", "free", "all", "direct"] = "paid"


class ReportCreate(BaseModel):
    """Создание отчета"""

    company_id: uuid.UUID
    state: ReportState


class NewReportRequest(BaseModel):
    """Новая схема для создания отчета (без legacy)."""

    attributes: List[str] = Field(default_factory=list, description="Атрибуты отчета")
    goals: List[Dict[str, str | int]] = Field(
        default_factory=list, description="Список ID целей"
    )
    metrics: List[str] = Field(default_factory=list, description="Метрики отчета")
    date_1: str = Field(..., description="Дата начала отчета")
    date_2: str = Field(..., description="Дата окончания отчета")
    # Основные параметры
    providers: List[ProviderSlug] = Field(
        default_factory=lambda: ["yandex_metrika"], description="Провайдеры данных"
    )
    traffic_kind: Literal["paid", "free", "all"] = Field(
        "paid", description="Тип трафика для всех провайдеров"
    )
    # Совместимость/расширения
    cpaGoalId: Optional[str] = Field(None, description="ID цели для CPA")
    cpoGoalId: Optional[str] = Field(None, description="ID цели для CPO")
    compare_date_1: Optional[str] = Field(None, description="Дата начала сравнения")
    compare_date_2: Optional[str] = Field(None, description="Дата окончания сравнения")


class CompareReportRequest(BaseModel):
    """Схема для создания отчета сравнения"""

    date_1: str = Field(..., description="Дата начала сравнения")
    date_2: str = Field(..., description="Дата окончания сравнения")


class NewReportCreate(BaseModel):
    """Новое создание отчета"""

    company_id: uuid.UUID
    request_data: NewReportRequest


class ReportDataPreview(BaseModel):
    """Превью данных отчета"""

    headers: List[str] = Field(default_factory=list, description="Заголовки таблицы")
    rows: List[List[Any]] = Field(
        default_factory=list, description="Первые 20 строк данных"
    )
    total_rows: Optional[int] = Field(
        None, description="Общее количество строк в файле"
    )


class ReportCompareItem(BaseModel):
    """Элемент массива сравнений отчета"""

    date_1: str = Field(..., description="Дата начала сравнения")
    date_2: str = Field(..., description="Дата окончания сравнения")
    created_at: datetime = Field(..., description="Дата создания сравнения")


class ReportResponse(BaseModel):
    """Ответ с отчетом"""

    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    status: str
    file_name: Optional[str] = None
    data_preview: Optional[ReportDataPreview] = Field(
        None, description="Превью данных отчета (первые 20 строк)"
    )
    source: str
    date_1: Optional[str] = None
    date_2: Optional[str] = None

    # Метрики и атрибуты
    goals: List[Dict[str, Any]] = Field(default_factory=list, description="Цели отчета")
    selected_metrics: List[str] = Field(
        default_factory=list, description="Выбранные метрики"
    )
    selected_attributes: List[str] = Field(
        default_factory=list, description="Выбранные атрибуты"
    )
    additional_metrics: Optional[str] = Field(
        None, description="Дополнительные метрики"
    )

    # Дополнительные поля
    compare_date_1: Optional[str] = Field(None, description="Дата начала сравнения")
    compare_date_2: Optional[str] = Field(None, description="Дата окончания сравнения")
    conclusion: Optional[str] = Field(None, description="Заключение отчета")
    conclusion_status: Optional[str] = Field(None, description="Статус заключения")
    user_waiting_for_conclusion: bool = Field(
        False, description="Ожидает ли пользователь заключения"
    )
    cpa_goal: Optional[str] = Field(None, description="Цель CPA")
    cpo_goal: Optional[str] = Field(None, description="Цель CPO")
    is_compared: bool = Field(False, description="Является ли отчетом сравнения")
    compares: Optional[List[ReportCompareItem]] = Field(
        None,
        description="Массив отчетов сравнения (доступно только с with_data_preview=True)",
    )

    class Config:
        from_attributes = True


class ReportConclusionUpdate(BaseModel):
    """Схема для обновления заключения отчета"""

    conclusion: str = Field(
        ..., min_length=1, max_length=10000, description="Заключение отчета"
    )


class ReportDeleteResponse(BaseModel):
    """Ответ на удаление отчета"""

    message: str = "Report deleted successfully"


class ReportConclusionUpdateResponse(BaseModel):
    """Ответ на обновление заключения отчета"""

    message: str = "Report conclusion updated successfully"


class ReportCreateResponse(BaseModel):
    """Ответ на создание отчета"""

    id: uuid.UUID
    status: str = "proceed"
    message: str = "Report created and queued for processing"


class ReportDownloadResponse(BaseModel):
    """Ответ с ссылкой для скачивания отчета"""

    download_url: str
    expires_in: int = 3600
    file_name: str


class ConclusionGenerateResponse(BaseModel):
    """Ответ на запуск генерации заключения"""

    message: str = "Conclusion generation started"
    report_id: uuid.UUID
    status: str = "proceed"


class ConclusionStatusResponse(BaseModel):
    """Статус генерации заключения"""

    report_id: uuid.UUID
    conclusion_status: str
    conclusion: Optional[str] = None
    user_waiting_for_conclusion: bool


class ConclusionRetryResponse(BaseModel):
    """Ответ на повторную генерацию заключения"""

    message: str = "Conclusion generation restarted"
    report_id: uuid.UUID
    status: str = "proceed"


class CompareReportResponse(BaseModel):
    """Ответ на создание отчета сравнения"""

    report_id: uuid.UUID
    message: str
    is_existing: bool = Field(
        ..., description="True если отчет уже существовал, False если создан новый"
    )


class ErrorResponse(BaseModel):
    """Общий ответ с ошибкой"""

    detail: str
