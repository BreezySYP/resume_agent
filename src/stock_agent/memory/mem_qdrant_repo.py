# src/stock_agent/memory/mem_qdrant_repo.py
"""记忆 Qdrant 仓储：检索 / 写入 / 状态更新。复用 service.qdrant_search + sql_helper。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pandas as pd
from loguru import logger
from qdrant_client import models

from memory.models import COLLECTION_NAME
from service.qdrant_search import search_dense, search_hybrid, upsert_hybrid_point
from service.sql_helper import attach_scores, fetch_by_ids
from shared.db.qdrant import get_qdrant_client

# MySQL 表名；若与 collection 同名可继续用 COLLECTION_NAME
MEMORY_TABLE = "agent_memories"


def build_memory_filter(
    user_id: str,
    namespace: Optional[str] = None,
    memory_types: Optional[list[str]] = None,
) -> models.Filter:
    must = [
        models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
        models.FieldCondition(key="status", match=models.MatchValue(value="active")),
    ]
    if namespace:
        must.append(
            models.FieldCondition(
                key="namespace", match=models.MatchValue(value=namespace)
            )
        )
    if memory_types:
        must.append(
            models.FieldCondition(
                key="memory_type", match=models.MatchAny(any=memory_types)
            )
        )
    return models.Filter(must=must)


def search_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
    namespace: Optional[str] = None,
    memory_types: Optional[list[str]] = None,
    use_hybrid: bool = True,
) -> pd.DataFrame:
    q_filter = build_memory_filter(user_id, namespace, memory_types)

    if use_hybrid:
        hits = search_hybrid(
            COLLECTION_NAME, query, top_k=top_k, query_filter=q_filter
        )
    else:
        hits = search_dense(
            COLLECTION_NAME, query, top_k=top_k, query_filter=q_filter
        )

    if hits is None or hits.empty:
        return pd.DataFrame()

    df = fetch_by_ids(MEMORY_TABLE, list(hits["id"]))
    if df is None or df.empty:
        return pd.DataFrame()

    if "status" in df.columns:
        df = df[df["status"] == "active"]

    return attach_scores(df, hits)


def build_memory_payload(
    *,
    memory_id: str,
    user_id: str,
    namespace: str,
    memory_type: str,
    status: str,
    source: str,
    importance: int,
    confidence: float,
    content_preview: str,
    created_at: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "memory_id": memory_id,
        "user_id": user_id,
        "namespace": namespace,
        "memory_type": memory_type,
        "status": status,
        "source": source,
        "importance": importance,
        "confidence": confidence,
        "created_at": created_at or datetime.utcnow().isoformat(),
        "expires_at": expires_at,
        "content_preview": (content_preview or "")[:200],
    }


def upsert_memory_point(
    *,
    point_id: str,
    content: str,
    payload: dict[str, Any],
) -> None:
    upsert_hybrid_point(
        collection=COLLECTION_NAME,
        point_id=point_id,
        text=content,
        payload=payload,
    )
    logger.debug("upsert memory point: {}", point_id)


def update_point_status(
    point_id: str,
    status: str,
    superseded_by: Optional[str] = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if superseded_by:
        payload["superseded_by"] = superseded_by

    get_qdrant_client().set_payload(
        collection_name=COLLECTION_NAME,
        payload=payload,
        points=[point_id],
    )