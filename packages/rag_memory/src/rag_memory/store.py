"""存储协议 + 内存实现（测试/轻量场景）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from rag_memory.schemas import MemoryCandidate, MemoryItem, MemoryStatus, MemoryTier

SORTABLE_FIELDS = {
    "created_at",
    "updated_at",
    "memory_type",
    "namespace",
    "importance",
    "confidence",
    "status",
}


def _sort_key(sort_by: str):
    """返回 MemoryItem → 排序值 的取数函数（memory_type 用 tier 值排序）。"""
    if sort_by not in SORTABLE_FIELDS:
        raise ValueError(f"unsupported sort_by: {sort_by!r}")

    def _key(item: MemoryItem):
        if sort_by == "created_at":
            return item.created_at
        if sort_by == "updated_at":
            return item.updated_at
        if sort_by == "memory_type":
            return item.tier.value
        if sort_by == "namespace":
            return item.namespace
        if sort_by == "importance":
            return item.importance
        if sort_by == "confidence":
            return item.confidence
        return item.status.value

    return _key


def sort_items(
    items: list[MemoryItem],
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[MemoryItem]:
    """稳定排序：NULL 统一排最后（先排非空组，再排空值组）。"""
    key = _sort_key(sort_by)
    non_null = [item for item in items if key(item) is not None]
    nulls = [item for item in items if key(item) is None]
    non_null.sort(key=key, reverse=(sort_order == "desc"))
    return non_null + nulls


class MemoryStore(Protocol):
    """记忆存储协议：由具体工程（Qdrant + MySQL 等）实现。"""

    def search(
        self,
        query: str,
        *,
        user_id: str,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 5,
    ) -> list[MemoryCandidate]:
        """按语义相关度返回候选（存储侧过滤 active + 未过期）。"""
        ...

    def save(self, item: MemoryItem) -> MemoryItem:
        """持久化一条记忆。"""
        ...

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        ...

    def find_by_content_hash(self, user_id: str, content_hash: str) -> Optional[MemoryItem]:
        ...

    def list_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> list[MemoryItem]:
        ...

    def count_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
    ) -> int:
        ...

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        ...

    def soft_delete(self, memory_id: str) -> None:
        ...


class InMemoryMemoryStore(MemoryStore):
    """基于 dict 的内存实现；search 用词重叠做确定性相关度，供测试与无外部依赖场景。"""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def _matches(
        self,
        item: MemoryItem,
        user_id: str,
        namespaces: Optional[list[str]],
        tiers: Optional[list[MemoryTier]],
    ) -> bool:
        return (
            item.user_id == user_id
            and item.status == MemoryStatus.ACTIVE
            and (item.expires_at is None or item.expires_at > datetime.utcnow())
            and (namespaces is None or item.namespace in namespaces)
            and (tiers is None or item.tier in tiers)
        )

    def search(
        self,
        query: str,
        *,
        user_id: str,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 5,
    ) -> list[MemoryCandidate]:
        q_terms = set(query.lower().split())
        scored: list[MemoryCandidate] = []
        for item in self._items.values():
            if not self._matches(item, user_id, namespaces, tiers):
                continue
            terms = set(item.content.lower().split())
            if not q_terms:
                relevance = 0.0
            else:
                overlap = len(q_terms & terms) / max(1, len(q_terms | terms))
                relevance = overlap
            scored.append(MemoryCandidate(item=item, relevance=relevance))
        scored.sort(key=lambda c: c.relevance, reverse=True)
        return scored[:limit]

    def save(self, item: MemoryItem) -> MemoryItem:
        now = datetime.utcnow()
        item.created_at = item.created_at or now
        item.updated_at = now
        self._items[item.id] = item
        return item

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        return self._items.get(memory_id)

    def find_by_content_hash(self, user_id: str, content_hash: str) -> Optional[MemoryItem]:
        for item in self._items.values():
            if item.user_id == user_id and item.content_hash == content_hash:
                return item
        return None

    def list_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> list[MemoryItem]:
        items = [
            item
            for item in self._items.values()
            if self._matches(item, user_id, namespaces, tiers)
        ]
        items = sort_items(items, sort_by=sort_by, sort_order=sort_order)
        return items[offset : offset + limit]

    def count_active(
        self,
        user_id: str,
        *,
        namespaces: Optional[list[str]] = None,
        tiers: Optional[list[MemoryTier]] = None,
    ) -> int:
        return sum(1 for item in self._items.values() if self._matches(item, user_id, namespaces, tiers))

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        item = self._items.get(old_id)
        if item is not None:
            item.status = MemoryStatus.SUPERSEDED
            item.superseded_by = new_id

    def soft_delete(self, memory_id: str) -> None:
        item = self._items.get(memory_id)
        if item is not None:
            item.status = MemoryStatus.DELETED
