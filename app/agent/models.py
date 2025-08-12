from typing import List
from pydantic import BaseModel, Field


class MetrikaDataNodeResponseFormat(BaseModel):
    """Один запрос к Yandex Metrika API"""

    metrics: List[str] = Field(
        ...,
        description="Список метрик для запроса",
        min_items=1,
        example=["ym:s:visits", "ym:s:users"],
    )

    dimensions: List[str] = Field(
        default=[],
        description="Список группировок для запроса",
        example=["ym:s:date", "ym:s:trafficSource"],
    )

    reason: str = Field(
        ...,
        description="Краткое обоснование запроса в одном предложении",
        min_length=10,
        max_length=200,
        example="Показать общее количество визитов и уникальных пользователей",
    )


class DateNodeResponseFormat(BaseModel):
    date_1: str
    date_2: str
