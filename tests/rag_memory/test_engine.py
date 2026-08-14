"""rag_memory.MemoryEngine 测试（InMemoryMemoryStore）。"""
from rag_memory.engine import MemoryEngine
from rag_memory.schemas import MemoryItem, MemoryQuery, MemoryStatus, MemoryTier
from rag_memory.store import InMemoryMemoryStore


def _item(
    content: str,
    *,
    user: str = "u1",
    tier: MemoryTier = MemoryTier.SEMANTIC,
    namespace: str = "user:u1:profile",
    importance: int = 3,
) -> MemoryItem:
    return MemoryItem(
        user_id=user,
        namespace=namespace,
        tier=tier,
        content=content,
        importance=importance,
    )


def test_add_empty_content_is_skipped():
    engine = MemoryEngine(InMemoryMemoryStore())
    result = engine.add(_item(content="   "))
    assert result.action == "skipped"


def test_add_same_content_is_deduplicated():
    engine = MemoryEngine(InMemoryMemoryStore())
    first = engine.add(_item(content="用户偏好稳健成长"))
    second = engine.add(_item(content="用户偏好稳健成长"))
    assert first.action == "created"
    assert second.action == "deduplicated"
    assert second.item.id == first.item.id


def test_add_similar_content_supersedes():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store, similar_threshold=0.7)
    old = engine.add(_item(content="a b c d"))
    new = engine.add(_item(content="a b c d e"))
    assert new.action == "superseded"
    assert new.replaced_id == old.item.id
    assert store.get(old.item.id).status == MemoryStatus.SUPERSEDED
    assert store.get(old.item.id).superseded_by == new.item.id


def test_episodic_ttl_applied_by_default():
    engine = MemoryEngine(InMemoryMemoryStore(), default_episodic_ttl_days=7)
    result = engine.add(
        _item(content="x y z", tier=MemoryTier.EPISODIC, namespace="user:u1:episode")
    )
    assert result.item.expires_at is not None


def test_search_filters_tiers_and_sets_score():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    engine.add(_item(content="茅台 白酒 龙头"))
    engine.add(
        _item(
            content="茅台 股价 上涨",
            tier=MemoryTier.EPISODIC,
            namespace="user:u1:episode",
        )
    )
    items = engine.search(
        MemoryQuery(user_id="u1", query="茅台 白酒", tiers=[MemoryTier.SEMANTIC], limit=5)
    )
    assert len(items) == 1
    assert items[0].tier == MemoryTier.SEMANTIC
    assert items[0].score is not None


def test_recall_important_injects_high_importance_memory():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    engine.add(
        _item(
            content="本季度 用户 持续 加仓 白酒",
            tier=MemoryTier.EPISODIC,
            namespace="user:u1:episode",
            importance=5,
        )
    )
    engine.add(
        _item(
            content="某次 技术面 超买 提示",
            tier=MemoryTier.EPISODIC,
            namespace="user:u1:episode",
            importance=1,
        )
    )
    items = engine.search(
        MemoryQuery(user_id="u1", query="技术面 超买", tiers=[MemoryTier.EPISODIC], limit=1),
        recall_important_top_k=1,
    )
    contents = [i.content for i in items]
    assert any("加仓 白酒" in c for c in contents), "高重要性记忆应被兜底注入"


def test_consolidate_creates_consolidated_memory():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    for i in range(3):
        engine.add(
            _item(
                content=f"episode {i} 分析结论",
                tier=MemoryTier.EPISODIC,
                namespace="user:u1:episode",
            )
        )
    created = engine.consolidate(
        "u1",
        namespaces=["user:u1:episode"],
        summarizer=lambda episodes: ["三轮总结：持续看多白酒"],
        min_items=3,
    )
    assert len(created) == 1
    assert created[0].tier == MemoryTier.CONSOLIDATED
    assert len(created[0].metadata["source_ids"]) == 3


def test_consolidate_requires_min_items():
    engine = MemoryEngine(InMemoryMemoryStore())
    created = engine.consolidate("u1", summarizer=lambda episodes: ["x"], min_items=3)
    assert created == []


def test_consolidate_without_summarizer_is_noop():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    for i in range(3):
        engine.add(
            _item(
                content=f"episode {i} 分析结论",
                tier=MemoryTier.EPISODIC,
                namespace="user:u1:episode",
            )
        )
    assert engine.consolidate("u1", namespaces=["user:u1:episode"]) == []


def test_search_no_candidates_returns_empty():
    engine = MemoryEngine(InMemoryMemoryStore())
    items = engine.search(MemoryQuery(user_id="ghost", query="anything", limit=5))
    assert items == []


def test_recall_important_works_without_relevant_candidates():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    engine.add(_item(content="用户只看成长股", importance=5))
    items = engine.search(
        MemoryQuery(user_id="u1", query="完全无关词", tiers=[MemoryTier.SEMANTIC], limit=2),
        recall_important_top_k=1,
    )
    assert len(items) == 1
    assert items[0].importance == 5


def test_consolidate_skips_empty_summaries():
    store = InMemoryMemoryStore()
    engine = MemoryEngine(store)
    for i in range(3):
        engine.add(
            _item(
                content=f"episode {i} 分析结论",
                tier=MemoryTier.EPISODIC,
                namespace="user:u1:episode",
            )
        )
    created = engine.consolidate(
        "u1",
        namespaces=["user:u1:episode"],
        summarizer=lambda episodes: ["", "  ", "有效摘要"],
        min_items=3,
    )
    assert len(created) == 1
    assert created[0].content == "有效摘要"
