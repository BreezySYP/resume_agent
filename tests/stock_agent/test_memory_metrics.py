"""memory Prometheus 埋点测试（默认 registry + 差值断言，不依赖 MySQL/Qdrant）。"""
from datetime import datetime, timedelta

import pandas as pd
import prometheus_client
import pytest
from memory.mem_service import MemoryService
from memory.models import MemoryCreate, MemoryRecord, MemoryStatus, MemoryType
from memory.store import StockMemoryStore
from rag_memory.schemas import MemoryItem, MemoryTier
from rag_memory.store import InMemoryMemoryStore


def _value(name: str, **labels) -> float:
    return prometheus_client.REGISTRY.get_sample_value(name, labels or None) or 0.0


def _svc(**kwargs) -> MemoryService:
    kwargs.setdefault("store", InMemoryMemoryStore())
    kwargs.setdefault("recall_important_top_k", 0)
    return MemoryService(**kwargs)


def test_add_records_operation_created_and_ttl():
    svc = _svc()
    before_ops = _value("memory_operations_total", operation="add", status="ok")
    before_writes = _value("memory_writes_total", memory_type="episode", action="created")
    before_ttl = _value("memory_ttl_seconds_count", memory_type="episode")

    svc.add_episode("u1", "第一轮结论")

    assert _value("memory_operations_total", operation="add", status="ok") - before_ops == 1
    assert _value("memory_writes_total", memory_type="episode", action="created") - before_writes == 1
    assert _value("memory_ttl_seconds_count", memory_type="episode") - before_ttl == 1


def test_deduplicated_action_counted_without_extra_ttl():
    svc = _svc()
    svc.add_episode("u1", "结论")
    before_dup = _value("memory_writes_total", memory_type="episode", action="deduplicated")
    before_ttl = _value("memory_ttl_seconds_count", memory_type="episode")

    svc.add_episode("u1", "结论")

    assert _value("memory_writes_total", memory_type="episode", action="deduplicated") - before_dup == 1
    assert _value("memory_ttl_seconds_count", memory_type="episode") == before_ttl


def test_superseded_action_counted():
    svc = _svc(similar_threshold=0.7)
    svc.add_episode("u1", "a b c d")
    before = _value("memory_writes_total", memory_type="episode", action="superseded")

    svc.add_episode("u1", "a b c d e")

    assert _value("memory_writes_total", memory_type="episode", action="superseded") - before == 1


def test_recall_miss_and_results_counted():
    svc = _svc()
    before_miss = _value("memory_recall_miss_total")
    before_results = _value("memory_recall_results_count_count")
    before_chars = _value("memory_recall_prompt_chars_count")

    text = svc.search_for_prompt("u1", "毫无相关的词")

    assert "暂无相关长期记忆" in text
    assert _value("memory_recall_miss_total") - before_miss == 1
    assert _value("memory_recall_results_count_count") - before_results == 1
    assert _value("memory_recall_prompt_chars_count") - before_chars == 1


def test_recall_with_results_does_not_count_miss():
    svc = _svc()
    svc.add_profile("u1", "用户偏好稳健成长")
    before_miss = _value("memory_recall_miss_total")
    before_results = _value("memory_recall_results_count_count")

    svc.search_for_prompt("u1", "偏好")

    assert _value("memory_recall_miss_total") == before_miss
    assert _value("memory_recall_results_count_count") - before_results == 1


def test_count_updates_active_gauge():
    svc = _svc()
    svc.add_profile("u1", "画像")
    svc.add_episode("u1", "事件")

    total = svc.count_memories("u1")

    assert total == 2
    assert _value("memory_active_count", memory_type="all") == 2


def test_consolidation_ok_and_output_counted():
    svc = _svc()
    for i in range(3):
        svc.add_episode("u1", f"第{i}轮 分析结论")
    before_runs = _value("memory_consolidation_runs_total", status="ok")
    before_output = _value("memory_consolidation_output_total")

    out = svc.consolidate("u1", summarizer=lambda records: ["三轮整合结论"], min_items=3)

    assert len(out) == 1
    assert _value("memory_consolidation_runs_total", status="ok") - before_runs == 1
    assert _value("memory_consolidation_output_total") - before_output == 1


def test_consolidation_error_counted():
    svc = _svc()
    for i in range(3):
        svc.add_episode("u1", f"第{i}轮 分析结论")
    before = _value("memory_consolidation_runs_total", status="error")

    def boom(records):
        raise RuntimeError("summarizer boom")

    with pytest.raises(RuntimeError):
        svc.consolidate("u1", summarizer=boom, min_items=3)

    assert _value("memory_consolidation_runs_total", status="error") - before == 1


def test_operation_error_counts_error_and_duration():
    class _BoomStore(InMemoryMemoryStore):
        def list_active(self, *args, **kwargs):
            raise RuntimeError("list boom")

    svc = MemoryService(store=_BoomStore(), recall_important_top_k=0)
    before_err = _value("memory_operations_total", operation="list", status="error")
    before_ok = _value("memory_operations_total", operation="list", status="ok")
    before_dur = _value("memory_operation_duration_seconds_count", operation="list")

    with pytest.raises(RuntimeError):
        svc.list_memories("u1")

    assert _value("memory_operations_total", operation="list", status="error") - before_err == 1
    assert _value("memory_operations_total", operation="list", status="ok") == before_ok
    assert _value("memory_operation_duration_seconds_count", operation="list") - before_dur == 1


class _FakeRepo:
    """仅用于 StockMemoryStore.save 的最小 repo 桩。"""

    def insert(self, data, memory_id=None, qdrant_point_id=None):
        return MemoryRecord(
            id=memory_id or "m-1",
            user_id=data.user_id,
            namespace=data.namespace,
            memory_type=data.memory_type,
            content=data.content,
            status=MemoryStatus.ACTIVE,
            confidence=data.confidence,
            importance=data.importance,
            source=data.source,
            qdrant_point_id=qdrant_point_id or "p-1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=data.expires_at,
        )


def test_vector_search_error_counted(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr("memory.store.search_hybrid", boom)
    store = StockMemoryStore(repo=_FakeRepo(), use_hybrid=True)
    before = _value("memory_vector_ops_total", operation="search", status="error")

    with pytest.raises(RuntimeError):
        store._search_df("query", user_id="u1", namespaces=None, tiers=None, limit=5)

    assert _value("memory_vector_ops_total", operation="search", status="error") - before == 1


def test_vector_search_ok_counted(monkeypatch):
    monkeypatch.setattr("memory.store.search_hybrid", lambda *a, **k: pd.DataFrame())
    store = StockMemoryStore(repo=_FakeRepo(), use_hybrid=True)
    before = _value("memory_vector_ops_total", operation="search", status="ok")

    df = store._search_df("query", user_id="u1", namespaces=None, tiers=None, limit=5)

    assert df.empty
    assert _value("memory_vector_ops_total", operation="search", status="ok") - before == 1


def test_vector_upsert_error_counted(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr("memory.store.upsert_hybrid_point", boom)
    store = StockMemoryStore(repo=_FakeRepo(), use_hybrid=True)
    item = MemoryItem(
        user_id="u1",
        namespace="user:u1:episode",
        tier=MemoryTier.EPISODIC,
        content="x",
    )
    before = _value("memory_vector_ops_total", operation="upsert", status="error")

    with pytest.raises(RuntimeError):
        store.save(item)

    assert _value("memory_vector_ops_total", operation="upsert", status="error") - before == 1


def test_vector_upsert_ok_counted(monkeypatch):
    monkeypatch.setattr("memory.store.upsert_hybrid_point", lambda *a, **k: None)
    store = StockMemoryStore(repo=_FakeRepo(), use_hybrid=True)
    item = MemoryItem(
        user_id="u1",
        namespace="user:u1:episode",
        tier=MemoryTier.EPISODIC,
        content="x",
    )
    before = _value("memory_vector_ops_total", operation="upsert", status="ok")

    store.save(item)

    assert _value("memory_vector_ops_total", operation="upsert", status="ok") - before == 1


def test_anomalous_ttl_only_counts_anomaly():
    svc = _svc()
    before_anomaly = _value("memory_anomalous_ttl_total", memory_type="episode")
    before_ttl = _value("memory_ttl_seconds_count", memory_type="episode")

    svc.add_memory(
        MemoryCreate(
            user_id="u1",
            namespace="user:u1:episode",
            memory_type=MemoryType.EPISODE,
            content="过期早于创建时间的脏数据",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
    )

    assert _value("memory_anomalous_ttl_total", memory_type="episode") - before_anomaly == 1
    assert _value("memory_ttl_seconds_count", memory_type="episode") == before_ttl
