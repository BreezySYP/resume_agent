"""stock_agent memory 领域门面测试（注入 InMemory 存储，不依赖 MySQL/Qdrant）。"""
from memory.mem_service import MemoryService
from memory.models import MemoryExtractItem, MemoryType
from rag_memory.store import InMemoryMemoryStore


def _svc() -> MemoryService:
    return MemoryService(store=InMemoryMemoryStore(), recall_important_top_k=0)


def test_add_and_recall_profile():
    svc = _svc()
    svc.add_profile("u1", "用户偏好稳健成长")
    ctx = svc.search_for_prompt("u1", "用户偏好")
    assert "用户偏好稳健成长" in ctx


def test_tier_mapping_survives_roundtrip():
    svc = _svc()
    record = svc.add_profile("u1", "用户只看成长股")
    assert record.memory_type == MemoryType.PROFILE
    assert record.importance == 4


def test_batch_extract_skips_empty_content():
    svc = _svc()
    items = [
        MemoryExtractItem(content="有效记忆", memory_type=MemoryType.PROFILE),
        MemoryExtractItem(content="   ", memory_type=MemoryType.EPISODE),
    ]
    saved = svc.add_from_extract_batch("u1", items)
    assert len(saved) == 1


def test_add_memory_empty_raises():
    from memory.dto import build_namespace
    from memory.models import MemoryCreate

    svc = _svc()
    data = MemoryCreate(
        user_id="u1",
        namespace=build_namespace("u1", MemoryType.PROFILE),
        memory_type=MemoryType.PROFILE,
        content="  ",
    )
    try:
        svc.add_memory(data)
    except ValueError:
        return
    raise AssertionError("空内容应抛出 ValueError")


def test_consolidate_via_service_produces_summary():
    svc = _svc()
    for i in range(3):
        svc.add_episode("u1", f"第{i}轮 分析结论")
    out = svc.consolidate(
        "u1",
        summarizer=lambda records: ["三轮整合结论"],
        min_items=3,
    )
    assert len(out) == 1
    assert out[0].memory_type == MemoryType.SUMMARY
