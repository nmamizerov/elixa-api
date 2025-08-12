from __future__ import annotations

from typing import List, Dict


def dedup_keep_order(items: List[str]) -> List[str]:
    """Удаляет дубликаты, сохраняя исходный порядок элементов."""
    return list(dict.fromkeys(items))


def build_selected_metrics(
    base_metrics: List[str],
    goal_metrics: List[str],
    selected_attributes: List[str],
    attributes_mapping: Dict[str, str],
) -> List[str]:
    """Формирует список метрик для запроса к провайдеру.

    Порядок: базовые → цели → метрики атрибутов. Дубликаты удаляются
    без нарушения порядка.
    """
    metrics: List[str] = []
    metrics.extend(base_metrics)
    metrics.extend(goal_metrics)

    for attr in selected_attributes:
        if attr in attributes_mapping:
            metrics.append(attributes_mapping[attr])

    return dedup_keep_order(metrics)
