# Яндекс.Метрика API URLs
CLIENTS_URL = "https://api-metrika.yandex.net/management/v1/clients"
GOALS_URL = "https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals"
API_URL = "https://api-metrika.yandex.ru/stat/v1/data"

# Ограничения API
MAX_METRICS_PER_REQUEST = 20
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1

# Базовые дополнительные метрики
BASE_ADDITIONAL_METRICS = ["cpc", "cr", "cpo", "cac", "romi", "drr", "roi"]

# Базовые дополнительные атрибуты
BASE_ADDITIONAL_ATTRIBUTES = [
    "clicks",
    "visits",
    "decline",
    "timeonsite",
    "depthofview",
]

# Метрики для платных отчетов (реклама)
PAID_METRICS = [
    "ym:ad:RUBConvertedAdCost",  # Расходы
    "ym:ad:ecommerceRUBConvertedRevenue",  # Выручка
]

# Метрики для бесплатных отчетов (органика)
FREE_METRICS = []

# Соответствие атрибутов метрикам для платного трафика
PAID_ATTRIBUTES_MAPPING = {
    "clicks": "ym:ad:clicks",
    "visits": "ym:ad:visits",
    "decline": "ym:ad:bounceRate",
    "timeonsite": "ym:ad:avgVisitDurationSeconds",
    "depthofview": "ym:ad:pageDepth",
}

# Соответствие атрибутов метрикам для бесплатного трафика
FREE_ATTRIBUTES_MAPPING = {
    "visits": "ym:s:visits",
    "decline": "ym:s:bounceRate",
    "timeonsite": "ym:s:avgVisitDurationSeconds",
    "depthofview": "ym:s:pageDepth",
}

# Русские названия метрик для платного трафика
PAID_METRIC_NAMES = {
    "ym:ad:RUBConvertedAdCost": "Расходы",
    "ym:ad:clicks": "Клики",
    "ym:ad:visits": "Визиты",
    "ym:ad:ecommerceRUBConvertedRevenue": "Выручка",
    "cpc": "CPC, ₽",
    "cr": "CR, %",
    "cpo": "CPO, ₽",
    "cpa": "CPA, ₽",
    "cac": "CAC, ₽",
    "romi": "ROMI, %",
    "drr": "ДРР, %",
    "roi": "ROI, %",
    "ym:ad:bounceRate": "Отказы, %",
    "ym:ad:avgVisitDurationSeconds": "Время на сайте, сек",
    "ym:ad:pageDepth": "Глубина просмотра",
}

# Русские названия метрик для бесплатного трафика
FREE_METRIC_NAMES = {
    "ym:s:visits": "Визиты",
    "ym:s:ecommerceRUBConvertedRevenue": "Выручка",
    "cpc": "CPC, ₽",
    "cr": "CR, %",
    "cpo": "CPO, ₽",
    "cpa": "CPA, ₽",
    "cac": "CAC, ₽",
    "romi": "ROMI, %",
    "drr": "ДРР, %",
    "roi": "ROI, %",
    "ym:s:bounceRate": "Отказы, %",
    "ym:s:avgVisitDurationSeconds": "Время на сайте, сек",
    "ym:s:pageDepth": "Глубина просмотра",
}

# Русские названия метрик для Direct отчетов
DIRECT_METRIC_NAMES = {
    "ym:ad:RUBConvertedAdCost": "Расходы",
    "ym:ad:clicks": "Клики",
    "ym:ad:visits": "Визиты",
    "ym:ad:ecommerceRUBConvertedRevenue": "Выручка",
    "cpc": "CPC, ₽",
    "cpa": "CPA, ₽",
    "cr": "CR, %",
    "cpo": "CPO, ₽",
    "cac": "CAC, ₽",
    "romi": "ROMI, %",
    "drr": "ДРР, %",
    "roi": "ROI, %",
    "ym:ad:bounceRate": "Отказы, %",
    "ym:ad:avgVisitDurationSeconds": "Время на сайте",
    "ym:ad:pageDepth": "Глубина просмотра",
}
