"""MemoryEngine：写入判断、检索判断、定期整合。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Callable, Optional

from rag_memory.schemas import (
    MemoryItem,
    MemoryQuery,
    MemoryTier,
    MemoryWriteResult,
)
from rag_memory.scoring import age_seconds, fusion_score, normalize_relevance
from rag_memory.store import MemoryStore

Consolidator = Callable[[list[MemoryItem]], list[str]]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class MemoryEngine:
    """分层记忆引擎（存储无关）。

    - 写入判断：空内容跳过 → content hash 去重 → 语义相似(≥ threshold)则 supersede 替换
    - 检索判断：融合打分 relevance×recency×importance；可选注入"重要记忆"兜底
    - 整合：把多条 EPISODIC 交给 LLM summarizer，产出 CONSOLIDATED 中期记忆
    """

    def __init__(
        self,
        store: MemoryStore,
        *,
        similar_threshold: float = 0.88,
        default_episodic_ttl_days: int = 30,
        half_life_days: float = 14.0,
        w_relevance: float = 0.6,
        w_recency: float = 0.25,
        w_importance: float = 0.15,
        recency_floor: float = 0.2,
    ) -> None:
        self.store = store
        self.similar_threshold = similar_threshold
        self.default_episodic_ttl_days = default_episodic_ttl_days
        self.half_life_days = half_life_days
        self.weights = (w_relevance, w_recency, w_importance)
        self.recency_floor = recency_floor

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def add(self, item: MemoryItem) -> MemoryWriteResult:
        content = (item.content or "").strip()
        if not content:
            return MemoryWriteResult(item=item, action="skipped")

        item.content = content
        item.content_hash = content_hash(content)
        if item.tier == MemoryTier.EPISODIC and item.expires_at is None:
            item.expires_at = datetime.utcnow() + timedelta(
                days=self.default_episodic_ttl_days
            )

        existing = self.store.find_by_content_hash(item.user_id, item.content_hash)
        if existing is not None and existing.is_active:
            return MemoryWriteResult(item=existing, action="deduplicated")

        candidates = self.store.search(
            content,
            user_id=item.user_id,
            namespaces=[item.namespace],
            tiers=[item.tier],
            limit=3,
        )
        if candidates:
            top = candidates[0]
            if top.relevance >= self.similar_threshold:
                return self._write_and_supersede(item, top.item)

        saved = self.store.save(item)
        return MemoryWriteResult(item=saved, action="created")

    def _write_and_supersede(
        self, item: MemoryItem, old: MemoryItem
    ) -> MemoryWriteResult:
        new = self.store.save(item)
        self.store.mark_superseded(old.id, new.id)
        return MemoryWriteResult(item=new, action="superseded", replaced_id=old.id)

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def search(
        self,
        query: MemoryQuery,
        *,
        recall_important_top_k: int = 0,
    ) -> list[MemoryItem]:
        """融合打分排序；可选注入高重要性记忆（与 query 无关兜底）。"""
        candidates = self.store.search(
            query.query,
            user_id=query.user_id,
            namespaces=query.namespaces,
            tiers=query.tiers,
            limit=query.limit,
        )
        if not candidates:
            relevant: list[MemoryItem] = []
        else:
            rel = normalize_relevance([c.relevance for c in candidates])
            now = datetime.utcnow()
            scored = [
                (
                    fusion_score(
                        r,
                        c.item.importance,
                        age_seconds(c.item.updated_at, now),
                        w_relevance=self.weights[0],
                        w_recency=self.weights[1],
                        w_importance=self.weights[2],
                        half_life_days=self.half_life_days,
                        recency_floor=self.recency_floor,
                    ),
                    c.item,
                )
                for c, r in zip(candidates, rel)
            ]
            scored.sort(key=lambda t: t[0], reverse=True)
            relevant = []
            for score, item in scored[: query.limit]:
                item.score = score
                relevant.append(item)

        if recall_important_top_k > 0:
            relevant = self._recall_important(
                query, relevant, top_k=recall_important_top_k
            )
        return relevant

    def _recall_important(
        self,
        query: MemoryQuery,
        already: list[MemoryItem],
        top_k: int,
    ) -> list[MemoryItem]:
        """注入与 query 无关但高重要性的记忆（MemGPT/Generative Agents 思路）。"""
        excluded = {item.id for item in already}
        important = self.store.list_active(
            query.user_id,
            namespaces=query.namespaces,
            tiers=query.tiers,
            limit=top_k * 3,
        )
        picked = [item for item in important if item.id not in excluded][:top_k]
        for item in picked:
            item.score = item.importance / 5.0
        return already + picked

    # ------------------------------------------------------------------
    # 整合（episodic → consolidated）
    # ------------------------------------------------------------------
    def consolidate(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        summarizer: Optional[Consolidator] = None,
        max_items: int = 20,
        min_items: int = 3,
    ) -> list[MemoryItem]:
        """对近期 EPISODIC 记忆调用 summarizer，产出 CONSOLIDATED 中期记忆。

        summarizer 返回若干条摘要文本；每条生成一条 CONSOLIDATED 记忆，
        并在 metadata.source_ids 中记录来源 episode。
        """
        if summarizer is None:
            return []
        episodes = self.store.list_active(
            user_id,
            namespaces=namespaces,
            tiers=[MemoryTier.EPISODIC],
            limit=max_items,
        )
        if len(episodes) < min_items:
            return []

        source_ids = [e.id for e in episodes]
        summaries = summarizer(episodes)
        created: list[MemoryItem] = []
        for text in summaries:
            text = (text or "").strip()
            if not text:
                continue
            item = MemoryItem(
                user_id=user_id,
                namespace=(namespaces[0] if namespaces else "episode"),
                tier=MemoryTier.CONSOLIDATED,
                content=text,
                importance=4,
                source="consolidation",
                metadata={"source_ids": source_ids},
            )
            result = self.add(item)
            if result.action != "skipped":
                created.append(result.item)
        return created
