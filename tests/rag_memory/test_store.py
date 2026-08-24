"""rag_memory.InMemoryMemoryStore 测试。"""
from datetime import datetime, timedelta

from rag_memory.engine import content_hash
from rag_memory.schemas import MemoryItem, MemoryStatus, MemoryTier
from rag_memory.store import InMemoryMemoryStore


def _item(content: str, *, tier: MemoryTier = MemoryTier.SEMANTIC, importance: int = 3) -> MemoryItem:
    return MemoryItem(
        user_id="u1",
        namespace="user:u1:profile",
        tier=tier,
        content=content,
        importance=importance,
    )


def test_search_empty_query_uses_zero_relevance():
    store = InMemoryMemoryStore()
    store.save(_item(content="abc def"))
    candidates = store.search("", user_id="u1")
    assert len(candidates) == 1
    assert candidates[0].relevance == 0.0


def test_search_filters_by_user_and_tier():
    store = InMemoryMemoryStore()
    store.save(_item(content="茅台 白酒 龙头"))
    store.save(
        _item(
            content="茅台 股价 上涨",
            tier=MemoryTier.EPISODIC,
        )
    )
    candidates = store.search(
        "茅台 白酒", user_id="u1", tiers=[MemoryTier.SEMANTIC], limit=5
    )
    assert len(candidates) == 1
    assert candidates[0].item.tier == MemoryTier.SEMANTIC
    assert store.search("茅台", user_id="ghost") == []


def test_find_by_content_hash():
    store = InMemoryMemoryStore()
    item = _item(content="hello world")
    item.content_hash = content_hash("hello world")
    saved = store.save(item)
    found = store.find_by_content_hash("u1", content_hash("hello world"))
    assert found is not None and found.id == saved.id
    assert store.find_by_content_hash("u1", "nope") is None


def test_list_active_sorts_by_importance_and_limits():
    store = InMemoryMemoryStore()
    low = store.save(_item(content="low importance", importance=1))
    high = store.save(_item(content="high importance", importance=5))
    items = store.list_active(
        "u1", limit=1, sort_by="importance", sort_order="desc"
    )
    assert [i.id for i in items] == [high.id]
    assert low.id != high.id


def test_list_active_sorts_by_created_at_desc_by_default_with_nulls_last():
    store = InMemoryMemoryStore()
    old = store.save(_item(content="old", importance=1))
    new = store.save(_item(content="new", importance=5))
    no_ts = _item(content="no timestamps", importance=3)
    no_ts.created_at = None
    no_ts.updated_at = None
    store.save(no_ts)
    no_ts.created_at = None
    no_ts.updated_at = None

    items = store.list_active("u1")
    assert [i.id for i in items] == [new.id, old.id, no_ts.id]


def test_list_active_paginates_with_offset():
    store = InMemoryMemoryStore()
    for i in range(5):
        store.save(_item(content=f"item {i}", importance=i + 1))

    items = store.list_active(
        "u1", limit=2, offset=2, sort_by="importance", sort_order="asc"
    )
    assert [i.importance for i in items] == [3, 4]


def test_expired_items_excluded_from_active_views():
    store = InMemoryMemoryStore()
    fresh = store.save(_item(content="有效记忆", tier=MemoryTier.EPISODIC))
    stale = _item(content="过期记忆", tier=MemoryTier.EPISODIC)
    stale.expires_at = datetime.utcnow() - timedelta(days=1)
    store.save(stale)

    assert [i.id for i in store.list_active("u1")] == [fresh.id]
    assert store.count_active("u1") == 1
    hits = store.search("过期记忆", user_id="u1")
    assert all(c.item.id != stale.id for c in hits)


def test_count_active():
    store = InMemoryMemoryStore()
    store.save(_item(content="a b"))
    store.save(
        _item(content="c d", tier=MemoryTier.EPISODIC)
    )
    assert store.count_active("u1") == 2
    assert store.count_active("u1", tiers=[MemoryTier.SEMANTIC]) == 1
    assert store.count_active("ghost") == 0


def test_mark_superseded_and_soft_delete():
    store = InMemoryMemoryStore()
    old = store.save(_item(content="旧记忆"))
    new = store.save(_item(content="新记忆"))
    store.mark_superseded(old.id, new.id)
    assert store.get(old.id).status == MemoryStatus.SUPERSEDED
    assert store.get(old.id).superseded_by == new.id
    store.soft_delete(new.id)
    assert store.get(new.id).status == MemoryStatus.DELETED


def test_status_ops_are_noop_for_missing_items():
    store = InMemoryMemoryStore()
    store.mark_superseded("missing", "new")
    store.soft_delete("missing")
    assert store.get("missing") is None
