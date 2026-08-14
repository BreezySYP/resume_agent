"""记忆存储适配层：Qdrant（混合向量）+ MySQL（元数据），实现 rag_memory.MemoryStore。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger
from memory.dto import (
    memory_item_to_create,
    memory_record_to_item,
    row_to_memory_record,
)
from memory.models import COLLECTION_NAME, MemoryStatus, memory_type_from_tier
from memory.mysql_repo import MemoryRepository
from qdrant_client import models
from rag_memory.schemas import MemoryCandidate, MemoryItem, MemoryTier
from service.qdrant_search import search_dense, search_hybrid, upsert_hybrid_point
from service.sql_helper import attach_scores, fetch_by_ids
from shared.db.qdrant import get_qdrant_client

MEMORY_TABLE = "agent_memories"


def _build_filter(
    user_id: str,
    namespaces: Optional[list[str]] = None,
    tiers: Optional[list[MemoryTier]] = None,
) -> models.Filter:
    must = [
        models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
        models.FieldCondition(key="status", match=models.MatchValue(value="active")),
    ]
    if namespaces:
        must.append(
            models.FieldCondition(
                key="namespace", match=models.MatchAny(any=namespaces)
            )
        )
    if tiers:
        types = [memory_type_from_tier(t).value for t in tiers]
        must.append(
            models.FieldCondition(
                key="memory_type", match=models.MatchAny(any=types)
            )
        )
    return models.Filter(must=must)


def _build_payload(item: MemoryItem) -> dict:
    return {
        "memory_id": item.id,
        "user_id": item.user_id,
        "namespace": item.namespace,
        "memory_type": memory_type_from_tier(item.tier).value,
        "tier": item.tier.value,
        "status": item.status.value,
        "source": item.source,
        "importance": item.importance,
        "confidence": item.confidence,
        "created_at": (item.created_at or datetime.utcnow()).isoformat(),
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "content_preview": item.content[:200],
    }


class StockMemoryStore:
    """Qdrant(混合检索) + MySQL(元数据/状态) 的 MemoryStore 实现。"""

    def __init__(
        self,
        repo: Optional[MemoryRepository] = None,
        *,
        use_hybrid: bool = True,
    ) -> None:
        self.repo = repo or MemoryRepository()
        self.use_hybrid = use_hybrid

    # --------------------------------------------------------------
    # 检索
    # --------------------------------------------------------------
    def _search_df(
        self,
        query: str,
        *,
        user_id: str,
        namespaces: Optional[list[str]],
        tiers: Optional[list[MemoryTier]],
        limit: int,
    ) -> pd.DataFrame:
        q_filter = _build_filter(user_id, namespaces, tiers)
        if self.use_hybrid:
            hits = search_hybrid(COLLECTION_NAME, query, top_k=limit, query_filter=q_filter)
        else:
            hits = search_dense(COLLECTION_NAME, query, top_k=limit, query_filter=q_filter)
        if hits is None or hits.empty:
            return pd.DataFrame()
        df = fetch_by_ids(MEMORY_TABLE, list(hits["id"]))
        if df is None or df.empty:
            return pd.DataFrame()
        if "status" in df.columns:
            df = df[df["status"] == "active"]
        return attach_scores(df, hits)

    def search(
        self,
        query: str,
        *,
        user_id: str,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 5,
    ) -> list[MemoryCandidate]:
        if not (query or "").strip():
            return []
        df = self._search_df(query, user_id=user_id, namespaces=namespaces, tiers=tiers, limit=limit)
        if df is None or df.empty:
            return []
        candidates: list[MemoryCandidate] = []
        for _, row in df.iterrows():
            raw = row.get("original_score") if hasattr(row, "get") else None
            try:
                score = float(raw) if raw is not None and raw == raw else 0.0
            except Exception:
                score = 0.0
            record = row_to_memory_record(row, score=score)
            candidates.append(
                MemoryCandidate(item=memory_record_to_item(record), relevance=score)
            )
        return candidates

    # --------------------------------------------------------------
    # 写入 / 状态
    # --------------------------------------------------------------
    def save(self, item: MemoryItem) -> MemoryItem:
        record = self.repo.insert(
            memory_item_to_create(item),
            memory_id=item.id,
            qdrant_point_id=item.vector_point_id or item.id,
        )
        point_id = record.qdrant_point_id or item.id
        try:
            upsert_hybrid_point(
                collection=COLLECTION_NAME,
                point_id=point_id,
                text=item.content,
                payload=_build_payload(item),
            )
        except Exception as e:
            logger.error("memory qdrant upsert failed id={}: {}", item.id, e)
            raise
        saved = memory_record_to_item(record)
        saved.vector_point_id = point_id
        return saved

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        record = self.repo.get_by_id(memory_id)
        return memory_record_to_item(record) if record else None

    def find_by_content_hash(self, user_id: str, content_hash: str) -> Optional[MemoryItem]:
        record = self.repo.find_by_content_hash(user_id, content_hash)
        return memory_record_to_item(record) if record else None

    def list_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        namespace = namespaces[0] if namespaces and len(namespaces) == 1 else None
        types = [memory_type_from_tier(t) for t in tiers] if tiers else None
        if types and len(types) > 1:
            merged: list[MemoryItem] = []
            for t in types:
                merged.extend(
                    memory_record_to_item(r)
                    for r in self.repo.list_active(
                        user_id, namespace=namespace, memory_type=t, limit=limit
                    )
                )
            merged.sort(key=lambda i: (i.importance, i.updated_at or datetime.min), reverse=True)
            return merged[:limit]
        records = self.repo.list_active(
            user_id,
            namespace=namespace,
            memory_type=types[0] if types else None,
            limit=limit,
        )
        return [memory_record_to_item(r) for r in records]

    def count_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
    ) -> int:
        return len(self.list_active(user_id, namespaces=namespaces, tiers=tiers, limit=1000))

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        old = self.get(old_id)
        if old is None:
            return
        self.repo.mark_superseded(old_id, new_id, old.user_id)
        try:
            get_qdrant_client().set_payload(
                collection_name=COLLECTION_NAME,
                payload={
                    "status": MemoryStatus.SUPERSEDED.value,
                    "superseded_by": new_id,
                },
                points=[old.vector_point_id or old_id],
            )
        except Exception as e:
            logger.warning("memory qdrant status update failed old={}: {}", old_id, e)

    def soft_delete(self, memory_id: str) -> None:
        old = self.get(memory_id)
        if old is None:
            return
        self.repo.soft_delete(memory_id, old.user_id)
