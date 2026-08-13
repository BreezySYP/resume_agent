# src/stock_agent/memory/models.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

COLLECTION_NAME = "agent_memories"

class MemoryType(str, Enum):
    PROFILE = "profile"          # 用户长期画像
    EPISODE = "episode"          # 中期会话/任务摘要
    PROCEDURAL = "procedural"    # 可复用分析规则/行为
    LESSON = "lesson"            # 教训（可并入 procedural）


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICT = "conflict"
    DELETED = "deleted"


class MemorySource(str, Enum):
    USER_EXPLICIT = "user_explicit"      # 用户明确说“记住”
    USER_FEEDBACK = "user_feedback"      # 用户纠错/反馈
    AGENT_INFERRED = "agent_inferred"    # Agent 自动提取
    SYSTEM = "system"


class MemoryCreate(BaseModel):
    """写入前的输入模型"""
    user_id: str
    namespace: str
    memory_type: MemoryType
    content: str
    source: MemorySource = MemorySource.AGENT_INFERRED
    source_thread_id: Optional[str] = None
    source_job_id: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: int = Field(default=3, ge=1, le=5)
    expires_at: Optional[datetime] = None
    object_key: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

class MemoryRecord(BaseModel):
    """完整记忆记录（MySQL + 业务使用）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    namespace: str
    memory_type: MemoryType
    content: str
    content_hash: Optional[str] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    superseded_by: Optional[str] = None
    confidence: float = 1.0
    importance: int = 3
    source: MemorySource = MemorySource.AGENT_INFERRED
    source_thread_id: Optional[str] = None
    source_job_id: Optional[str] = None
    qdrant_point_id: Optional[str] = None
    object_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None

    # 检索时可能带上的相似度
    score: Optional[float] = None
    
class MemoryExtractItem(BaseModel):
    """
    单条 LLM 提取出的记忆。
    对应 with_structured_output / 工具返回的结构。
    """
    content: str = Field(..., description="记忆正文，简洁、可复用")
    memory_type: MemoryType = Field(
        ..., description="profile / episode / procedural / lesson"
    )
    source: MemorySource = Field(
        default=MemorySource.AGENT_INFERRED,
        description="来源：user_explicit / user_feedback / agent_inferred / system",
    )
    importance: int = Field(default=3, ge=1, le=5, description="重要性 1-5")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度 0-1")
    source_thread_id: Optional[str] = None
    source_job_id: Optional[str] = None
    expires_at: Optional[datetime] = Field(
        default=None, description="仅 episode 需要时可填"
    )
    metadata: Optional[dict[str, Any]] = None


class MemoryExtractResult(BaseModel):
    """一次提取的多条记忆（LLM 顶层结构）"""
    items: list[MemoryExtractItem] = Field(default_factory=list)