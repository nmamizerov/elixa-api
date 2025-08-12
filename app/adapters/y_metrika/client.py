import asyncio
from typing import Dict, List, Optional, Tuple, Literal
import httpx
from loguru import logger

from app.core.config import settings
from app.core.constants import (
    API_URL,
    CLIENTS_URL,
    GOALS_URL,
    MAX_METRICS_PER_REQUEST,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
)
from app.core.utils import merge_metric_batches
from app.database.models.integration import YandexMetrikaIntegration
from app.schemas.report import MetrikaApiRequest, MetrikaApiResponse


class YandexMetrikaClient:
    """Клиент для работы с API Яндекс.Метрики"""

    def __init__(self):
        self.forms_counter = "65643403"
        self.forms_token = (
            settings.forms_token if hasattr(settings, "forms_token") else None
        )
        self.ym_token = (
            settings.elixa_ai_token if hasattr(settings, "elixa_ai_token") else None
        )

    def _get_token(self, yandexMetrikaIntegration: YandexMetrikaIntegration) -> str:
        """Получение правильного токена для компании"""
        if (
            yandexMetrikaIntegration.counter_id == self.forms_counter
            and self.forms_token
        ):
            return self.forms_token

        if not yandexMetrikaIntegration.token:
            raise ValueError(
                "Компания не настроена для работы с Яндекс.Метрикой. Необходимо добавить токен."
            )

        return yandexMetrikaIntegration.token

    def _validate_company_setup(
        self, yandexMetrikaIntegration: YandexMetrikaIntegration
    ) -> None:
        """Проверка, что компания настроена для работы с Яндекс.Метрикой"""
        if not yandexMetrikaIntegration.counter_id:
            raise ValueError(
                "Компания не настроена для работы с Яндекс.Метрикой. Необходимо добавить счетчик."
            )

        if not yandexMetrikaIntegration.token:
            raise ValueError(
                "Компания не настроена для работы с Яндекс.Метрикой. Необходимо добавить токен."
            )

    async def get_metrika_data(
        self,
        dimensions: List[str],
        metrics: List[str],
        date_1: str,
        date_2: str,
        yandexMetrikaIntegration: YandexMetrikaIntegration,
        filters: Optional[str] = None,
        direct_client_logins: Optional[str] = None,
    ) -> Optional[MetrikaApiResponse]:
        """Получение данных из Яндекс.Метрики с поддержкой пакетных запросов"""
        # Проверяем, что компания настроена для работы с Яндекс.Метрикой
        self._validate_company_setup(yandexMetrikaIntegration)

        logger.info(f"🔹 Getting metrika data for {dimensions} with {metrics} metrics")

        if len(metrics) <= MAX_METRICS_PER_REQUEST:
            return await self._single_request(
                dimensions,
                metrics,
                date_1,
                date_2,
                yandexMetrikaIntegration,
                filters,
                direct_client_logins,
            )
        else:
            return await self._batch_requests(
                dimensions,
                metrics,
                date_1,
                date_2,
                yandexMetrikaIntegration,
                filters,
                direct_client_logins,
            )

    async def _single_request(
        self,
        dimensions: List[str],
        metrics: List[str],
        date_1: str,
        date_2: str,
        yandexMetrikaIntegration: YandexMetrikaIntegration,
        filters: Optional[str] = None,
        direct_client_logins: Optional[str] = None,
    ) -> Optional[MetrikaApiResponse]:
        """Выполнение одиночного запроса к API"""

        params = {
            "ids": yandexMetrikaIntegration.counter_id,
            "dimensions": ",".join(dimensions),
            "metrics": ",".join(metrics),
            "date1": date_1,
            "date2": date_2,
            "limit": 100,
            "offset": 1,
            "attribution": "CROSS_DEVICE_LAST_SIGNIFICANT",
            "group": "day",
            "currency": "RUB",
        }

        if filters:
            params["filters"] = filters
        if direct_client_logins:
            params["direct_client_logins"] = direct_client_logins

        token = self._get_token(yandexMetrikaIntegration)
        headers = {"Authorization": f"Bearer {token}"}

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(API_URL, params=params, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        return MetrikaApiResponse(**data)
                    else:
                        logger.error(
                            f"API Error {response.status_code}: {response.text}"
                        )
                        return None

            except httpx.ReadTimeout:
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    logger.warning(
                        f"Timeout attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}"
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error("Max timeout attempts reached")
                    return None

    async def _batch_requests(
        self,
        dimensions: List[str],
        metrics: List[str],
        date_1: str,
        date_2: str,
        yandexMetrikaIntegration: YandexMetrikaIntegration,
        filters: Optional[str] = None,
        direct_client_logins: Optional[str] = None,
    ) -> Optional[MetrikaApiResponse]:
        """Выполнение пакетных запросов для большого количества метрик"""

        logger.info(f"Splitting request into batches, total metrics: {len(metrics)}")

        # Разбиваем метрики на пачки
        metric_batches = [
            metrics[i : i + MAX_METRICS_PER_REQUEST]
            for i in range(0, len(metrics), MAX_METRICS_PER_REQUEST)
        ]

        logger.info(f"Total batches: {len(metric_batches)}")

        # Получаем результат первой пачки
        first_batch_response = await self._single_request(
            dimensions,
            metric_batches[0],
            date_1,
            date_2,
            yandexMetrikaIntegration,
            filters,
            direct_client_logins,
        )

        if not first_batch_response or not first_batch_response.data:
            logger.error("Failed to get data for first batch")
            return None

        base_result = first_batch_response.model_dump()
        batch_results = []

        # Получаем результаты остальных пачек
        for i, metric_batch in enumerate(metric_batches[1:], 1):
            logger.info(f"Processing batch {i + 1}/{len(metric_batches)}")

            batch_response = await self._single_request(
                dimensions,
                metric_batch,
                date_1,
                date_2,
                yandexMetrikaIntegration,
                filters,
                direct_client_logins,
            )

            if batch_response and batch_response.data:
                batch_results.append(batch_response.model_dump())

        # Объединяем результаты
        merged_result = merge_metric_batches(base_result, batch_results)

        # Обновляем метаданные о метриках
        if "query" in merged_result:
            merged_result["query"]["metrics"] = metrics

        return MetrikaApiResponse(**merged_result)

    async def get_clients(
        self, yandexMetrikaIntegration: YandexMetrikaIntegration
    ) -> Optional[Dict]:
        """Получение списка клиентов"""
        self._validate_company_setup(yandexMetrikaIntegration)
        token = self._get_token(yandexMetrikaIntegration)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                CLIENTS_URL,
                params={"counters": yandexMetrikaIntegration.counter_id},
                headers=headers,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error {response.status_code}: {response.text}")
                return None

    async def get_goals(
        self, yandexMetrikaIntegration: YandexMetrikaIntegration
    ) -> Optional[Dict]:
        """Получение списка целей"""
        self._validate_company_setup(yandexMetrikaIntegration)
        token = self._get_token(yandexMetrikaIntegration)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOALS_URL.format(counter_id=yandexMetrikaIntegration.counter_id),
                headers=headers,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error {response.status_code}: {response.text}")
                return None

    async def get_goal_names(self, goals: List[Dict[str, str]]) -> Dict[str, str]:
        """Получение названий целей по их ID"""
        goal_names = {}

        for goal in goals:
            goal_id = goal["id"]
            goal_name = goal["name"]
            goal_metric = f"ym:ad:goal{goal_id}users"
            goal_names[goal_metric] = f"Конверсии ({goal_name})"

        return goal_names

    async def get_goal_metrics(
        self,
        goals: List[Dict[str, str]],
        traffic_type: Literal["paid", "free"],
    ) -> Tuple[List[str], Dict[str, str]]:
        """Формирование метрик по целям"""
        goal_metrics = []
        goal_names = {}

        for goal in goals:
            goal_id = goal["id"]
            goal_name = goal["name"]
            if traffic_type == "paid":
                goal_metrics.extend(
                    [f"ym:ad:goal{goal_id}visits", f"ym:ad:goal{goal_id}conversionRate"]
                )
                goal_names[f"ym:ad:goal{goal_id}visits"] = (
                    f"Достижения цели {goal_name}"
                )
                goal_names[f"ym:ad:goal{goal_id}conversionRate"] = (
                    f"Конверсия в цель {goal_name}, %"
                )
            else:  # free
                goal_metrics.extend(
                    [f"ym:s:goal{goal_id}visits", f"ym:s:goal{goal_id}conversionRate"]
                )
                goal_names[f"ym:s:goal{goal_id}visits"] = f"Достижения цели {goal_name}"
                goal_names[f"ym:s:goal{goal_id}conversionRate"] = (
                    f"Конверсия в цель {goal_name}, %"
                )

        # Получаем реальные названия целей
        real_goal_names = await self.get_goal_names(goals)
        goal_names.update(real_goal_names)

        return goal_metrics, goal_names


metrika_client = YandexMetrikaClient()
