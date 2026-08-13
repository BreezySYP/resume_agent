# src/stock_agent/memory/mem_service.py
"""记忆业务编排：检索、写入、冲突更新。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from loguru import logger

from memory.mem_qdrant_repo import (
    build_memory_payload,
    search_memories,
    update_point_status,
    upsert_memory_point,
)

from memory.dto import (
    build_namespace,
    extract_item_to_create,
    records_to_prompt_text,
    row_to_memory_record,
)

from memory.models import (
    MemoryCreate,
    MemoryExtractItem,
    MemoryRecord,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from memory.mysql_repo import MemoryRepository


class MemoryService:
    def __init__(
        self,
        repo: Optional[MemoryRepository] = None,
        *,
        similar_threshold: float = 0.88,
        use_hybrid: bool = True,
        default_episode_days: int = 30,
    ):
        self.repo = repo or MemoryRepository()
        self.similar_threshold = similar_threshold
        self.use_hybrid = use_hybrid
        self.default_episode_days = default_episode_days

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

        types = [t.value for t in memory_types] if memory_types else None
        df = search_memories(
            user_id=user_id,
            query=query,
            top_k=limit,
            namespace=namespace,
            memory_types=types,
            use_hybrid=self.use_hybrid,
        )
        if df is None or df.empty:
            return []

        records: list[MemoryRecord] = []
        for _, row in df.iterrows():
            score = row.get("original_score") if hasattr(row, "get") else row["original_score"]
            try:
                score = float(score) if score is not None and score == score else None
            except Exception:
                score = None
            records.append(row_to_memory_record(row, score=score))
        return records

    def search_for_prompt(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 5,
    ) -> str:
        items = self.search(
            user_id=user_id,
            query=query,
            memory_types=[
                MemoryType.PROFILE,
                MemoryType.EPISODE,
                MemoryType.PROCEDURAL,
            ],
            limit=limit,
        )
        if not items:
            return "（暂无相关长期记忆）"

        return records_to_prompt_text(items)

        
    # ------------------------------------------------------------------
    # 写入：统一走 MemoryExtractItem（LLM 结构化结果）
    # ------------------------------------------------------------------
    def add_from_extract(
        self,
        user_id: str,
        item: MemoryExtractItem,
    ) -> MemoryRecord:
        """LLM 提取单条记忆后的标准写入入口。"""
        data = extract_item_to_create(user_id, item)
        return self.add_memory(data)

    def add_from_extract_batch(
        self,
        user_id: str,
        items: list[MemoryExtractItem],
    ) -> list[MemoryRecord]:
        """一次提取多条时批量写入。"""
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

        if data.memory_type == MemoryType.EPISODE and data.expires_at is None:
            data.expires_at = datetime.utcnow() + timedelta(
                days=self.default_episode_days
            )

        similar = self.search(
            user_id=data.user_id,
            query=content,
            namespace=data.namespace,
            memory_types=[data.memory_type],
            limit=3,
        )
        top = similar[0] if similar else None
        if (
            top is not None
            and top.score is not None
            and top.score >= self.similar_threshold
        ):
            logger.info(
                "memory supersede old={} score={:.3f} user={}",
                top.id,
                top.score,
                data.user_id,
            )
            return self._write_and_supersede(data, top)

        return self._write_new(data)

    # 便捷方法：内部仍构造 MemoryExtractItem，避免 **kw
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
    # 内部写入
    # ------------------------------------------------------------------
    def _write_new(self, data: MemoryCreate) -> MemoryRecord:
        memory_id = str(uuid4())
        record = self.repo.insert(
            data, memory_id=memory_id, qdrant_point_id=memory_id
        )

        payload = build_memory_payload(
            memory_id=memory_id,
            user_id=data.user_id,
            namespace=data.namespace,
            memory_type=data.memory_type.value,
            status=MemoryStatus.ACTIVE.value,
            source=data.source.value,
            importance=data.importance,
            confidence=data.confidence,
            content_preview=data.content,
            created_at=(record.created_at or datetime.utcnow()).isoformat(),
            expires_at=record.expires_at.isoformat() if record.expires_at else None,
        )
        try:
            upsert_memory_point(
                point_id=memory_id,
                content=data.content,
                payload=payload,
            )
        except Exception as e:
            logger.error("qdrant upsert failed memory_id={}: {}", memory_id, e)
            raise

        return record

    def _write_and_supersede(
        self, data: MemoryCreate, old: MemoryRecord
    ) -> MemoryRecord:
        new_record = self._write_new(data)
        self.repo.mark_superseded(
            old_id=old.id, new_id=new_record.id, user_id=data.user_id
        )
        try:
            update_point_status(
                point_id=old.qdrant_point_id or old.id,
                status=MemoryStatus.SUPERSEDED.value,
                superseded_by=new_record.id,
            )
        except Exception as e:
            logger.warning("update qdrant status failed old={}: {}", old.id, e)
        return new_record


if __name__ == "__main__":
    svc = MemoryService(use_hybrid=True)

    from shared.db.qdrant import ensure_hybrid_collection, get_qdrant_client
    from shared.models.ollama_models import get_embedding_dim
    from memory.models import COLLECTION_NAME
    dim = get_embedding_dim()
    ensure_hybrid_collection(get_qdrant_client(), collection=COLLECTION_NAME, dim=dim)
    # 模拟 LLM 结构化输出
    extracted = MemoryExtractItem(
        content="用户风险偏好较低，偏好稳健成长。",
        memory_type=MemoryType.PROFILE,
        source=MemorySource.AGENT_INFERRED,
        importance=4,
        confidence=0.9,
        source_thread_id="thread_001",
    )
    svc.add_from_extract("u_10086", extracted)

    ctx = svc.search_for_prompt(
        "u_10086", "下半年AI应用有哪些适合稳健投资者的标的？"
    )
    
    print(ctx)