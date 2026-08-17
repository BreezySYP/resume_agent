"""记忆业务门面：领域类型 <-> rag_memory 通用引擎。

职责边界：
- 通用算法（分层、融合打分、去重/替换判断、整合）在 `packages/rag_memory`。
- 本模块只做：MemoryType/MemoryRecord 等领域的双向往返、默认参数、便捷方法。
"""
from __future__ import annotations

from typing import Callable, Optional

from memory.dto import (
    build_namespace,
    extract_item_to_create,
    memory_create_to_item,
    memory_item_to_record,
    records_to_prompt_text,
)
from memory.models import (
    MemoryCreate,
    MemoryExtractItem,
    MemoryRecord,
    MemorySource,
    MemoryType,
    memory_tier,
)
from memory.mysql_repo import MemoryRepository
from memory.store import StockMemoryStore
from rag_memory.engine import MemoryEngine
from rag_memory.schemas import MemoryQuery, MemoryTier
from rag_memory.store import MemoryStore

Consolidator = Callable[[list[MemoryRecord]], list[str]]


class MemoryService:
    """领域门面：保持旧的公共 API，内部委托 rag_memory.MemoryEngine。"""

    def __init__(
        self,
        repo: Optional[MemoryRepository] = None,
        *,
        store: Optional[MemoryStore] = None,
        similar_threshold: float = 0.88,
        use_hybrid: bool = True,
        default_episode_days: int = 30,
        recall_important_top_k: int = 1,
    ) -> None:
        self.store = store or StockMemoryStore(repo, use_hybrid=use_hybrid)
        self.engine = MemoryEngine(
            self.store,
            similar_threshold=similar_threshold,
            default_episodic_ttl_days=default_episode_days,
        )
        self.recall_important_top_k = recall_important_top_k

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def search(
        self,
        user_id: str,
        query: str,
        *,
        memory_types: Optional[list[MemoryType]] = None,
        namespace: Optional[str] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        if not (query or "").strip():
            return []
        tiers = [memory_tier(t) for t in memory_types] if memory_types else None
        items = self.engine.search(
            MemoryQuery(
                user_id=user_id,
                query=query,
                namespaces=[namespace] if namespace else None,
                tiers=tiers,
                limit=limit,
            ),
            recall_important_top_k=0,
        )
        return [memory_item_to_record(i) for i in items]

    def search_for_prompt(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> str:
        """supervisor 注入用：语义相关 + 高重要性记忆兜底。"""
        items = self.engine.search(
            MemoryQuery(
                user_id=user_id,
                query=query or "",
                tiers=[
                    MemoryTier.SEMANTIC,
                    MemoryTier.EPISODIC,
                    MemoryTier.PROCEDURAL,
                    MemoryTier.CONSOLIDATED,
                ],
                limit=limit,
            ),
            recall_important_top_k=self.recall_important_top_k,
        )
        return records_to_prompt_text([memory_item_to_record(i) for i in items])

    def list_memories(
        self,
        user_id: str,
        *,
        memory_type: Optional[MemoryType] = None,
        namespace: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """列出用户全部有效记忆（active），可选按类型/命名空间过滤。"""
        tiers = [memory_tier(memory_type)] if memory_type else None
        namespaces = [namespace] if namespace else None
        items = self.store.list_active(
            user_id,
            namespaces=namespaces,
            tiers=tiers,
            limit=limit,
        )
        return [memory_item_to_record(i) for i in items]

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def add_from_extract(
        self,
        user_id: str,
        item: MemoryExtractItem,
    ) -> MemoryRecord:
        """LLM 结构化单条记忆的标准写入入口。"""
        data = extract_item_to_create(user_id, item)
        return self.add_memory(data)

    def add_from_extract_batch(
        self,
        user_id: str,
        items: list[MemoryExtractItem],
    ) -> list[MemoryRecord]:
        results: list[MemoryRecord] = []
        for item in items:
            content = (item.content or "").strip()
            if not content:
                continue
            results.append(self.add_from_extract(user_id, item))
        return results

    def add_memory(self, data: MemoryCreate) -> MemoryRecord:
        content = (data.content or "").strip()
        if not content:
            raise ValueError("memory content is empty")
        if not data.namespace:
            data.namespace = build_namespace(data.user_id, data.memory_type)

        item = memory_create_to_item(data)
        result = self.engine.add(item)
        return memory_item_to_record(result.item)

    def add_profile(
        self,
        user_id: str,
        content: str,
        item: Optional[MemoryExtractItem] = None,
    ) -> MemoryRecord:
        if item is None:
            item = MemoryExtractItem(
                content=content,
                memory_type=MemoryType.PROFILE,
                source=MemorySource.AGENT_INFERRED,
                importance=4,
                confidence=0.9,
            )
        else:
            item = item.model_copy(
                update={
                    "content": content or item.content,
                    "memory_type": MemoryType.PROFILE,
                }
            )
        return self.add_from_extract(user_id, item)

    def add_episode(
        self,
        user_id: str,
        content: str,
        item: Optional[MemoryExtractItem] = None,
    ) -> MemoryRecord:
        if item is None:
            item = MemoryExtractItem(
                content=content,
                memory_type=MemoryType.EPISODE,
                source=MemorySource.AGENT_INFERRED,
                importance=3,
                confidence=0.8,
            )
        else:
            item = item.model_copy(
                update={
                    "content": content or item.content,
                    "memory_type": MemoryType.EPISODE,
                }
            )
        return self.add_from_extract(user_id, item)

    def add_procedural(
        self,
        user_id: str,
        content: str,
        item: Optional[MemoryExtractItem] = None,
    ) -> MemoryRecord:
        if item is None:
            item = MemoryExtractItem(
                content=content,
                memory_type=MemoryType.PROCEDURAL,
                source=MemorySource.AGENT_INFERRED,
                importance=4,
                confidence=0.85,
            )
        else:
            item = item.model_copy(
                update={
                    "content": content or item.content,
                    "memory_type": MemoryType.PROCEDURAL,
                }
            )
        return self.add_from_extract(user_id, item)

    # ------------------------------------------------------------------
    # 整合：episode → summary（中期记忆）
    # ------------------------------------------------------------------
    def consolidate(
        self,
        user_id: str,
        *,
        summarizer: Optional[Consolidator] = None,
        min_items: int = 3,
    ) -> list[MemoryRecord]:
        """把近期 EPISODE 交给 summarizer(records) -> [摘要文本]，产出 SUMMARY 记忆。"""

        def _adapter(episodes):
            return summarizer([memory_item_to_record(e) for e in episodes])

        items = self.engine.consolidate(
            user_id,
            summarizer=_adapter if summarizer is not None else None,
            min_items=min_items,
        )
        return [memory_item_to_record(i) for i in items]
