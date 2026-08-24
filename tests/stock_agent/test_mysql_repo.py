"""MemoryRepository 过期过滤测试（SQLite 内存库，不依赖 MySQL）。"""
from datetime import datetime, timedelta
from hashlib import sha256

import sqlalchemy as sa
from memory.models import MemoryCreate, MemoryType
from memory.mysql_repo import MemoryRepository

CREATE_TABLE_SQL = """
CREATE TABLE agent_memories (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    namespace VARCHAR(128) NOT NULL,
    memory_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    superseded_by VARCHAR(36),
    confidence DECIMAL(3, 2),
    importance INTEGER,
    source VARCHAR(32) NOT NULL DEFAULT 'agent_inferred',
    source_thread_id VARCHAR(64),
    source_job_id VARCHAR(64),
    qdrant_point_id VARCHAR(36),
    object_key VARCHAR(512),
    created_at DATETIME,
    updated_at DATETIME,
    expires_at DATETIME,
    metadata TEXT
)
"""


def _repo() -> MemoryRepository:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text(CREATE_TABLE_SQL))
    return MemoryRepository(eng=engine)


def _create(content: str, *, expires_at: datetime | None) -> MemoryCreate:
    return MemoryCreate(
        user_id="u1",
        namespace="user:u1:episode",
        memory_type=MemoryType.EPISODE,
        content=content,
        expires_at=expires_at,
    )


def test_list_active_excludes_expired():
    repo = _repo()
    repo.insert(_create("未过期", expires_at=datetime.utcnow() + timedelta(days=1)))
    repo.insert(_create("已过期", expires_at=datetime.utcnow() - timedelta(days=1)))
    repo.insert(_create("永不过期", expires_at=None))

    records = repo.list_active("u1")
    assert {r.content for r in records} == {"未过期", "永不过期"}


def test_count_active_excludes_expired():
    repo = _repo()
    repo.insert(_create("未过期", expires_at=datetime.utcnow() + timedelta(days=1)))
    repo.insert(_create("已过期", expires_at=datetime.utcnow() - timedelta(days=1)))

    assert repo.count_active("u1") == 1


def test_find_by_content_hash_ignores_expired():
    repo = _repo()
    repo.insert(_create("重复内容", expires_at=datetime.utcnow() - timedelta(days=1)))
    repo.insert(_create("其他内容", expires_at=datetime.utcnow() + timedelta(days=1)))

    def _h(content: str) -> str:
        return sha256(content.strip().encode("utf-8")).hexdigest()

    assert repo.find_by_content_hash("u1", _h("重复内容")) is None
    assert repo.find_by_content_hash("u1", _h("其他内容")) is not None
