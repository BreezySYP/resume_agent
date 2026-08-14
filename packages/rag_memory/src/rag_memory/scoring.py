"""融合打分：relevance × recency × importance（纯函数，便于单测）。"""
from __future__ import annotations

from datetime import datetime

_SECONDS_PER_DAY = 86400.0


def recency_weight(
    age_seconds: float,
    half_life_days: float = 14.0,
    floor: float = 0.2,
) -> float:
    """指数衰减：越新越接近 1，最终收敛到 floor。"""
    if age_seconds <= 0:
        return 1.0
    half_life = half_life_days * _SECONDS_PER_DAY
    decay = 0.5 ** (age_seconds / half_life)
    return floor + (1.0 - floor) * decay


def importance_boost(importance: int, max_boost: float = 0.5) -> float:
    """重要性 1-5 映射到 [0, max_boost]。"""
    importance = max(1, min(5, int(importance)))
    return max_boost * (importance - 1) / 4.0


def fusion_score(
    relevance: float,
    importance: int,
    age_seconds: float,
    *,
    w_relevance: float = 0.6,
    w_recency: float = 0.25,
    w_importance: float = 0.15,
    half_life_days: float = 14.0,
    recency_floor: float = 0.2,
) -> float:
    """融合打分：score = w_r·relevance + w_rec·recency + w_imp·importance_boost。

    relevance 应在 [0, 1]（调用方可先用 min-max 归一化），
    recency 与 importance_boost 均由本函数保证在 [0, 1] 内。
    """
    relevance = max(0.0, min(1.0, float(relevance)))
    recency = recency_weight(age_seconds, half_life_days, recency_floor)
    imp = importance_boost(importance)
    return (
        w_relevance * relevance
        + w_recency * recency
        + w_importance * imp
    )


def age_seconds(dt: datetime | None, now: datetime | None = None) -> float:
    """记忆年龄（秒）；未知时间按 0 处理（最新）。"""
    if dt is None:
        return 0.0
    now = now or datetime.utcnow()
    return max(0.0, (now - dt).total_seconds())


def normalize_relevance(values: list[float]) -> list[float]:
    """min-max 归一化到 [0, 1]；全相等时返回 1.0。"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]
