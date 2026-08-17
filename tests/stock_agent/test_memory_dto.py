"""memory.dto 的 DTO/类型转换逻辑测试。"""
import json

import pandas as pd
import pytest
from memory.dto import (
    _get,
    _parse_metadata,
    _safe_float,
    _safe_int,
    _safe_str,
    build_namespace,
    extract_item_to_create,
    records_to_prompt_text,
    row_to_memory_record,
)
from memory.models import (
    MemoryCreate,
    MemoryExtractItem,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from pydantic import ValidationError


def test_memory_type_values():
    assert MemoryType.PROFILE.value == "profile"
    assert MemoryType.EPISODE.value == "episode"
    assert MemoryType.PROCEDURAL.value == "procedural"


def test_memory_create_validation_bounds():
    with pytest.raises(ValidationError):
        MemoryCreate(user_id="u", namespace="n", memory_type=MemoryType.EPISODE, content="c", confidence=1.5)
    with pytest.raises(ValidationError):
        MemoryCreate(user_id="u", namespace="n", memory_type=MemoryType.EPISODE, content="c", importance=6)


def test_get_helpers():
    assert _get({"a": 1}, "a") == 1
    assert _get({"a": 1}, "missing", "d") == "d"
    series = pd.Series({"a": 1, "b": 2})
    assert _get(series, "a") == 1
    assert _get(series, "missing", "d") == "d"


def test_safe_number_helpers():
    assert _safe_float(None) == 1.0
    assert _safe_float(float("nan")) == 1.0
    assert _safe_float("0.5") == 0.5
    assert _safe_float("bad") == 1.0
    assert _safe_int(None) == 3
    assert _safe_int("2") == 2
    assert _safe_int(float("nan")) == 3
    assert _safe_str(None) == ""
    assert _safe_str(123) == "123"


def test_parse_metadata():
    assert _parse_metadata(None) is None
    assert _parse_metadata(float("nan")) is None
    assert _parse_metadata({"k": "v"}) == {"k": "v"}
    assert _parse_metadata(json.dumps({"k": "v"})) == {"k": "v"}
    assert _parse_metadata("not-json") is None


def test_build_namespace():
    assert build_namespace("u1", MemoryType.PROFILE) == "user:u1:profile"
    assert build_namespace("u1", MemoryType.EPISODE) == "user:u1:episode"


def test_extract_item_to_create():
    item = MemoryExtractItem(
        content=" 喜欢低估值蓝筹 ",
        memory_type=MemoryType.PROFILE,
        importance=4,
        confidence=0.9,
    )
    created = extract_item_to_create("u1", item)
    assert isinstance(created, MemoryCreate)
    assert created.content == "喜欢低估值蓝筹"
    assert created.namespace == "user:u1:profile"
    assert created.source == MemorySource.AGENT_INFERRED


def test_row_to_memory_record_from_dict():
    row = {
        "id": "1",
        "user_id": "u1",
        "namespace": "user:u1:episode",
        "memory_type": "episode",
        "content": "内容",
        "status": "active",
        "confidence": 0.9,
        "importance": 4,
        "source": "agent_inferred",
        "metadata": '{"k": "v"}',
        "original_score": 0.95,
    }
    record = row_to_memory_record(row)
    assert record.memory_type == MemoryType.EPISODE
    assert record.status == MemoryStatus.ACTIVE
    assert record.source == MemorySource.AGENT_INFERRED
    assert record.metadata == {"k": "v"}
    assert record.score == 0.95


def test_row_to_memory_record_from_series_and_nan_score():
    row = pd.Series({"id": "2", "user_id": "u2", "content": "c", "original_score": float("nan")})
    record = row_to_memory_record(row)
    assert record.score is None
    assert record.memory_type == MemoryType.EPISODE  # 默认值


def test_records_to_prompt_text():
    assert records_to_prompt_text([]) == "（暂无相关长期记忆）"

    from memory.models import MemoryRecord

    records = [
        MemoryRecord(user_id="u", namespace="n", memory_type=MemoryType.PROFILE, content="偏好低估值", score=0.87654),
        MemoryRecord(user_id="u", namespace="n", memory_type=MemoryType.EPISODE, content="结论：看好新能源"),
    ]
    text = records_to_prompt_text(records)
    assert "1. [semantic|0.877] 偏好低估值" in text
    assert "2. [episodic|-] 结论：看好新能源" in text
