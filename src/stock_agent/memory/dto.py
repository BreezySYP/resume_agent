# src/stock_agent/memory/dto.py
"""记忆相关 DTO 与类型转换（row / LLM 结构 → 领域模型）。"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Union

import pandas as pd

from memory.models import (
    MemoryCreate,
    MemoryExtractItem,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)

RowLike = Union[Mapping[str, Any], pd.Series, dict]


def _get(row: RowLike, key: str, default: Any = None) -> Any:
    if isinstance(row, pd.Series):
        return row[key] if key in row.index else default
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


def _parse_metadata(raw: Any) -> Optional[dict[str, Any]]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None


def _safe_float(v: Any, default: float = 1.0) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 3) -> int:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return int(v)
    except Exception:
        return default


def _safe_str(v: Any, default: str = "") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    return str(v)


def row_to_memory_record(row: RowLike, *, score: Optional[float] = None) -> MemoryRecord:
    """
    MySQL 行 / pandas Series → MemoryRecord。
    score 可由检索结果 original_score 传入。
    """
    raw_score = score
    if raw_score is None:
        raw_score = _get(row, "original_score")
    try:
        parsed_score = (
            float(raw_score)
            if raw_score is not None and raw_score == raw_score
            else None
        )
    except Exception:
        parsed_score = None

    status_raw = _safe_str(_get(row, "status"), "active")
    source_raw = _safe_str(_get(row, "source"), MemorySource.AGENT_INFERRED.value)
    type_raw = _safe_str(_get(row, "memory_type"), MemoryType.EPISODE.value)

    return MemoryRecord(
        id=_safe_str(_get(row, "id")),
        user_id=_safe_str(_get(row, "user_id")),
        namespace=_safe_str(_get(row, "namespace")),
        memory_type=MemoryType(type_raw),
        content=_safe_str(_get(row, "content")),
        content_hash=_get(row, "content_hash"),
        status=MemoryStatus(status_raw),
        superseded_by=_get(row, "superseded_by"),
        confidence=_safe_float(_get(row, "confidence"), 1.0),
        importance=_safe_int(_get(row, "importance"), 3),
        source=MemorySource(source_raw),
        source_thread_id=_get(row, "source_thread_id"),
        source_job_id=_get(row, "source_job_id"),
        qdrant_point_id=_get(row, "qdrant_point_id"),
        object_key=_get(row, "object_key"),
        created_at=_get(row, "created_at"),
        updated_at=_get(row, "updated_at"),
        expires_at=_get(row, "expires_at"),
        metadata=_parse_metadata(_get(row, "metadata")),
        score=parsed_score,
    )


def build_namespace(user_id: str, memory_type: MemoryType) -> str:
    mapping = {
        MemoryType.PROFILE: "profile",
        MemoryType.EPISODE: "episode",
        MemoryType.PROCEDURAL: "procedural",
        MemoryType.LESSON: "procedural",
    }
    suffix = mapping.get(memory_type, memory_type.value)
    return f"user:{user_id}:{suffix}"


def extract_item_to_create(
    user_id: str,
    item: MemoryExtractItem,
    *,
    namespace: Optional[str] = None,
) -> MemoryCreate:
    """LLM 结构化单条记忆 → MemoryCreate。"""
    return MemoryCreate(
        user_id=user_id,
        namespace=namespace or build_namespace(user_id, item.memory_type),
        memory_type=item.memory_type,
        content=(item.content or "").strip(),
        source=item.source,
        source_thread_id=item.source_thread_id,
        source_job_id=item.source_job_id,
        importance=item.importance,
        confidence=item.confidence,
        expires_at=item.expires_at,
        metadata=item.metadata,
    )


def records_to_prompt_text(records: list[MemoryRecord]) -> str:
    """检索结果 → Supervisor 注入文本。"""
    if not records:
        return "（暂无相关长期记忆）"
    lines = []
    for i, m in enumerate(records, 1):
        score = f"{m.score:.3f}" if m.score is not None else "-"
        lines.append(f"{i}. [{m.memory_type.value}|{score}] {m.content}")
    return "\n".join(lines)