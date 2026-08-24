# src/stock_agent/memory/mysql_repo.py
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from memory.dto import row_to_memory_record
from memory.models import (
    MemoryCreate,
    MemoryRecord,
    MemoryType,
)
from sqlalchemy import text
from sqlalchemy.engine import Engine

SORTABLE_COLUMNS = {
    "created_at": "created_at",
    "updated_at": "updated_at",
    "memory_type": "memory_type",
    "namespace": "namespace",
    "importance": "importance",
    "confidence": "confidence",
    "status": "status",
}

# 允许为 NULL 的排序字段：NULL 统一排在最后
NULLABLE_SORT_COLUMNS = {"created_at", "updated_at", "importance", "confidence"}

# 有效期过滤：expires_at 为 NULL 表示长期有效，否则必须晚于当前时间
ACTIVE_EXPIRY_CLAUSE = "(expires_at IS NULL OR expires_at > :now)"


def _active_query_clauses(user_id: str) -> tuple[list[str], dict[str, Any]]:
    """active 记忆的统一查询条件：状态 active + 未过期。"""
    clauses = ["user_id = :user_id", "status = 'active'", ACTIVE_EXPIRY_CLAUSE]
    params: dict[str, Any] = {"user_id": user_id, "now": datetime.utcnow()}
    return clauses, params


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _order_by_clause(sort_by: str, sort_order: str) -> str:
    if sort_by not in SORTABLE_COLUMNS:
        raise ValueError(f"unsupported sort_by: {sort_by!r}")
    column = SORTABLE_COLUMNS[sort_by]
    direction = "ASC" if sort_order == "asc" else "DESC"
    parts: list[str] = []
    if sort_by in NULLABLE_SORT_COLUMNS:
        # 先按“是否为空”排序，保证 NULL 永远排在最后
        parts.append(f"({column} IS NULL)")
    parts.append(f"{column} {direction}")
    parts.append("id ASC")  # 稳定排序，保证分页不重不漏
    return ", ".join(parts)


def _default_engine() -> Engine:
    """惰性加载默认 engine：避免 import 时连接 MySQL（可测性/启动速度）。"""
    from shared.db.mysql import engine

    return engine


class MemoryRepository:
    def __init__(self, eng: Engine | None = None):
        self.engine = eng or _default_engine()

    def insert(self, data: MemoryCreate, memory_id: Optional[str] = None,
               qdrant_point_id: Optional[str] = None) -> MemoryRecord:
        mid = memory_id or str(uuid4())
        ch = _content_hash(data.content)
        meta_json = json.dumps(data.metadata, ensure_ascii=False) if data.metadata else None

        sql = text("""
            INSERT INTO agent_memories (
                id, user_id, namespace, memory_type, content, content_hash,
                status, confidence, importance, source,
                source_thread_id, source_job_id, qdrant_point_id,
                object_key, expires_at, metadata
            ) VALUES (
                :id, :user_id, :namespace, :memory_type, :content, :content_hash,
                'active', :confidence, :importance, :source,
                :source_thread_id, :source_job_id, :qdrant_point_id,
                :object_key, :expires_at, :metadata
            )
        """)
        params = {
            "id": mid,
            "user_id": data.user_id,
            "namespace": data.namespace,
            "memory_type": data.memory_type.value,
            "content": data.content,
            "content_hash": ch,
            "confidence": data.confidence,
            "importance": data.importance,
            "source": data.source.value,
            "source_thread_id": data.source_thread_id,
            "source_job_id": data.source_job_id,
            "qdrant_point_id": qdrant_point_id or mid,
            "object_key": data.object_key,
            "expires_at": data.expires_at,
            "metadata": meta_json,
        }
        with self.engine.begin() as conn:
            conn.execute(sql, params)

        return self.get_by_id(mid)

    def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        sql = text("SELECT * FROM agent_memories WHERE id = :id")
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"id": memory_id}).mappings().first()
        return row_to_memory_record(row) if row else None

    def list_active(
        self,
        user_id: str,
        namespace: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> list[MemoryRecord]:
        clauses, params = _active_query_clauses(user_id)
        params.update({"limit": limit, "offset": offset})
        if namespace:
            clauses.append("namespace = :namespace")
            params["namespace"] = namespace
        if memory_type:
            clauses.append("memory_type = :memory_type")
            params["memory_type"] = memory_type.value

        where = " AND ".join(clauses)
        sql = text(f"""
            SELECT * FROM agent_memories
            WHERE {where}
            ORDER BY {_order_by_clause(sort_by, sort_order)}
            LIMIT :limit OFFSET :offset
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
        return [row_to_memory_record(r) for r in rows]

    def count_active(
        self,
        user_id: str,
        *,
        namespace: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> int:
        """统计符合过滤条件的 active 记忆总数（分页用）。"""
        clauses, params = _active_query_clauses(user_id)
        if namespace:
            clauses.append("namespace = :namespace")
            params["namespace"] = namespace
        if memory_type:
            clauses.append("memory_type = :memory_type")
            params["memory_type"] = memory_type.value

        sql = text(f"SELECT COUNT(*) FROM agent_memories WHERE {' AND '.join(clauses)}")
        with self.engine.connect() as conn:
            return int(conn.execute(sql, params).scalar_one())

    def mark_superseded(self, old_id: str, new_id: str, user_id: str) -> None:
        sql = text("""
            UPDATE agent_memories
            SET status = 'superseded', superseded_by = :new_id
            WHERE id = :old_id AND status = 'active'
        """)
        with self.engine.begin() as conn:
            conn.execute(sql, {"old_id": old_id, "new_id": new_id})

    def soft_delete(self, memory_id: str, user_id: str) -> None:
        sql = text("""
            UPDATE agent_memories
            SET status = 'deleted'
            WHERE id = :id
        """)
        with self.engine.begin() as conn:
            conn.execute(sql, {"id": memory_id})

    def find_by_content_hash(self, user_id: str, content_hash: str) -> Optional[MemoryRecord]:
        sql = text("""
            SELECT * FROM agent_memories
            WHERE user_id = :user_id AND content_hash = :h
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > :now)
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(
                sql,
                {"user_id": user_id, "h": content_hash, "now": datetime.utcnow()},
            ).mappings().first()
        return row_to_memory_record(row) if row else None
