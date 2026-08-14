# src/stock_agent/memory/mysql_repo.py
from __future__ import annotations

import hashlib
import json
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


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _default_engine() -> Engine:
    """惰性加载默认 engine：避免 import 时连接 MySQL（可测性/启动速度）。"""
    from shared.db.mysql import engine

    return engine


class MemoryRepository:
    def __init__(self, eng: Engine | None = None):
        self.engine = eng or _default_engine()

    def create_tables(self) -> None:
        """幂等建表"""
        ddl_main = """
            CREATE TABLE IF NOT EXISTS agent_memories (
                id              VARCHAR(36)  NOT NULL PRIMARY KEY,
                user_id         VARCHAR(64)  NOT NULL,
                namespace        VARCHAR(128) NOT NULL,
                memory_type     VARCHAR(32)  NOT NULL,
                content         TEXT         NOT NULL,
                content_hash    CHAR(64)     DEFAULT NULL,
                status          VARCHAR(20)  NOT NULL DEFAULT 'active',
                superseded_by   VARCHAR(36)  DEFAULT NULL,
                confidence      DECIMAL(3,2) DEFAULT 1.00,
                importance      TINYINT      DEFAULT 3,
                source          VARCHAR(32)  NOT NULL DEFAULT 'agent_inferred',
                source_thread_id VARCHAR(64) DEFAULT NULL,
                source_job_id   VARCHAR(64)  DEFAULT NULL,
                qdrant_point_id VARCHAR(36)  DEFAULT NULL,
                object_key      VARCHAR(512) DEFAULT NULL,
                created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                updated_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                                ON UPDATE CURRENT_TIMESTAMP(3),
                expires_at      DATETIME(3)  DEFAULT NULL,
                metadata        JSON         DEFAULT NULL,
                INDEX idx_user_ns_status (user_id, namespace, status),
                INDEX idx_user_type_status (user_id, memory_type, status),
                INDEX idx_status_expires (status, expires_at),
                INDEX idx_content_hash (content_hash),
                INDEX idx_superseded_by (superseded_by)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

        with self.engine.begin() as conn:
            conn.execute(text(ddl_main))

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

    def get_active_by_ids(self, ids: list[str]) -> list[MemoryRecord]:
        if not ids:
            return []
        # 简单实现：逐个或 IN 查询
        placeholders = ", ".join([f":id{i}" for i in range(len(ids))])
        params = {f"id{i}": vid for i, vid in enumerate(ids)}
        sql = text(f"""
            SELECT * FROM agent_memories
            WHERE id IN ({placeholders}) AND status = 'active'
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
        return [row_to_memory_record(r) for r in rows]

    def list_active(
        self,
        user_id: str,
        namespace: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        clauses = ["user_id = :user_id", "status = 'active'"]
        params: dict[str, Any] = {"user_id": user_id, "limit": limit}
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
            ORDER BY updated_at DESC
            LIMIT :limit
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).mappings().all()
        return [row_to_memory_record(r) for r in rows]

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

    def update_qdrant_point_id(self, memory_id: str, point_id: str) -> None:
        sql = text("""
            UPDATE agent_memories
            SET qdrant_point_id = :point_id
            WHERE id = :id
        """)
        with self.engine.begin() as conn:
            conn.execute(sql, {"id": memory_id, "point_id": point_id})

    def find_by_content_hash(self, user_id: str, content_hash: str) -> Optional[MemoryRecord]:
        sql = text("""
            SELECT * FROM agent_memories
            WHERE user_id = :user_id AND content_hash = :h AND status = 'active'
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"user_id": user_id, "h": content_hash}).mappings().first()
        return row_to_memory_record(row) if row else None


if __name__ == "__main__":
    repo = MemoryRepository()
    repo.create_tables()
