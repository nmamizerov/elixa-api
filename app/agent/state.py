from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict

from app.agent.models import MetrikaDataNodeResponseFormat
from app.schemas.company import Company


class AgentState(TypedDict):
    """Состояние агента для анализа Яндекс.Метрики"""

    # Входящий запрос пользователя
    user_message: str

    # История чата для контекста
    chat_history: List[Dict[str, str]]

    # Ответ от LLM
    assistant_response: str

    # Дополнительные метаданные
    metadata: Dict[str, Any]

    # Компания пользователя для доступа к Яндекс.Метрике
    company: Optional[Company]

    # Даты для запроса к Яндекс.Метрике
    date_1: str
    date_2: str
    metrika_data_params: MetrikaDataNodeResponseFormat
    metrika_data: Any
