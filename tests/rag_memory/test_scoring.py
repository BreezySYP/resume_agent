"""rag_memory.scoring 纯函数测试。"""
from datetime import datetime, timedelta

import pytest
from rag_memory.scoring import (
    age_seconds,
    fusion_score,
    importance_boost,
    normalize_relevance,
    recency_weight,
)


def test_recency_weight_decays_towards_floor():
    assert recency_weight(0) == 1.0
    recent = recency_weight(60)
    old = recency_weight(86400 * 30)
    assert recent >= old
    assert old >= 0.2 - 1e-9


def test_importance_boost_is_monotonic():
    assert importance_boost(1) == 0.0
    assert importance_boost(5) == 0.5
    assert importance_boost(3) < importance_boost(4)


def test_fusion_score_stays_in_bounds():
    for relevance in (0.0, 0.5, 1.0):
        for importance in (1, 3, 5):
            s = fusion_score(relevance, importance, age_seconds=3600)
            assert 0.0 <= s <= 1.0


def test_fusion_score_prefers_newer_and_important():
    old = fusion_score(0.8, 3, age_seconds=86400 * 60)
    new = fusion_score(0.8, 3, age_seconds=60)
    important = fusion_score(0.8, 5, age_seconds=86400 * 60)
    assert new > old
    assert important > old


def test_normalize_relevance_minmax():
    assert normalize_relevance([0.2, 0.6, 1.0]) == pytest.approx([0.0, 0.5, 1.0])
    assert normalize_relevance([0.5, 0.5]) == [1.0, 1.0]
    assert normalize_relevance([]) == []


def test_age_seconds_never_negative():
    future = datetime.utcnow() + timedelta(days=1)
    assert age_seconds(future) == 0.0
    assert age_seconds(None) == 0.0
