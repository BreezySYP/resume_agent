"""api/memory_router.py — 用户记忆列表 API"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from memory.mem_service import MemoryService
from memory.models import MemoryRecord, MemorySource, MemoryStatus, MemoryType
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["Memory"])

# 列表接口返回的记忆正文最大长度，超出部分截断并置 content_truncated=True
MAX_MEMORY_CONTENT_CHARS = 200


class MemoryListItem(BaseModel):
    id: str
    user_id: str
    namespace: str
    memory_type: MemoryType
    content: str
    content_truncated: bool = False
    importance: int
    confidence: float
    status: MemoryStatus
    source: MemorySource
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class MemoryListResponse(BaseModel):
    total: int
    items: list[MemoryListItem]


def _memory_service() -> MemoryService:
    return MemoryService(use_hybrid=True)


def _truncate_content(content: str, max_chars: int = MAX_MEMORY_CONTENT_CHARS) -> tuple[str, bool]:
    content = (content or "").strip()
    if len(content) <= max_chars:
        return content, False
    return content[:max_chars].rstrip() + "…", True


def _to_memory_list_item(record: MemoryRecord) -> MemoryListItem:
    content, truncated = _truncate_content(record.content)
    return MemoryListItem(
        id=record.id,
        user_id=record.user_id,
        namespace=record.namespace,
        memory_type=record.memory_type,
        content=content,
        content_truncated=truncated,
        importance=record.importance,
        confidence=record.confidence,
        status=record.status,
        source=record.source,
        created_at=record.created_at,
        updated_at=record.updated_at,
        expires_at=record.expires_at,
    )


@router.get(
    "/users/{user_id}/memories",
    response_model=MemoryListResponse,
    summary="列出用户全部记忆",
)
async def list_user_memories(
    user_id: str,
    limit: int = Query(50, ge=1, le=500, description="最多返回条数"),
    memory_type: Optional[MemoryType] = Query(None, description="按记忆类型过滤"),
    namespace: Optional[str] = Query(None, description="按命名空间过滤"),
    service: MemoryService = Depends(_memory_service),
) -> MemoryListResponse:
    records = service.list_memories(
        user_id,
        memory_type=memory_type,
        namespace=namespace,
        limit=limit,
    )
    items = [_to_memory_list_item(r) for r in records]
    return MemoryListResponse(total=len(items), items=items)
