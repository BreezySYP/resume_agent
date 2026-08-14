"""rag_memory — 数据模型。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryTier(str, Enum):
    """记忆分层：短 / 中 / 长期。

    - WORKING：会话内工作记忆（由上层用上下文/Redis 维护，本引擎不落盘）
    - EPISODIC：短期情景记忆（单轮/单任务摘要，通常带 TTL）
    - CONSOLIDATED：中期整合记忆（对若干 episode 提炼后的结论）
    - SEMANTIC：长期语义事实（用户画像、偏好、约束，通常不设 TTL）
    - PROCEDURAL：长期程序性记忆（可复用的分析方法 / 经验 / 教训）
    """

    WORKING = "working"
    EPISODIC = "episodic"
    CONSOLIDATED = "consolidated"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"  # 已被新记忆取代（保留用于审计）
    CONFLICT = "conflict"      # LLM 判定为冲突，等待人工/下次处理
    DELETED = "deleted"


class MemoryItem(BaseModel):
    """一条通用记忆记录（存储无关）。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    namespace: str
    tier: MemoryTier
    content: str
    content_hash: Optional[str] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    superseded_by: Optional[str] = None
    importance: int = Field(default=3, ge=1, le=5)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: str = "agent"
    source_thread_id: Optional[str] = None
    source_job_id: Optional[str] = None
    vector_point_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
    score: Optional[float] = Field(
        default=None, description="检索时的融合打分（写入时为 None）"
    )

    @property
    def is_active(self) -> bool:
        now = datetime.utcnow()
        return self.status == MemoryStatus.ACTIVE and (
            self.expires_at is None or self.expires_at > now
        )


class MemoryCandidate(BaseModel):
    """检索候选：记忆 + 存储返回的语义相关度。"""

    item: MemoryItem
    relevance: float = Field(ge=0.0, description="向量检索原始相关度（存储相关，可能为 RRF/余弦）")


class MemoryQuery(BaseModel):
    user_id: str
    query: str = ""
    namespaces: Optional[list[str]] = None
    tiers: Optional[list[MemoryTier]] = None
    limit: int = 5


class MemoryWriteResult(BaseModel):
    """add() 的写入结果与动作。"""

    item: MemoryItem
    action: str  # created | superseded | deduplicated | skipped
    replaced_id: Optional[str] = None
