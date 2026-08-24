"""stock_agent memory list API 测试（注入 InMemory 存储，不依赖 MySQL/Qdrant）。"""
from datetime import datetime, timedelta

from api.memory_router import _memory_service, router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from memory.mem_service import MemoryService
from memory.models import MemoryExtractItem, MemoryType
from rag_memory.store import InMemoryMemoryStore


def _svc() -> MemoryService:
    return MemoryService(store=InMemoryMemoryStore(), recall_important_top_k=0)


def _client(svc: MemoryService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_memory_service] = lambda: svc
    return TestClient(app)


def test_list_user_memories():
    svc = _svc()
    svc.add_profile("u1", "用户偏好稳健成长")
    svc.add_episode("u1", "第一轮结论")

    resp = _client(svc).get("/api/ai/users/u1/memories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["memory_type"] for item in body["items"]} == {"profile", "episode"}
    assert all(item["content_truncated"] is False for item in body["items"])
    assert all(item["user_id"] == "u1" for item in body["items"])


def test_list_user_memories_filters_by_type_and_limit():
    svc = _svc()
    svc.add_profile("u1", "画像")
    svc.add_episode("u1", "事件1")
    svc.add_episode("u1", "事件2")
    client = _client(svc)

    body = client.get("/api/ai/users/u1/memories", params={"memory_type": "episode"}).json()
    assert body["total"] == 2
    assert all(item["memory_type"] == "episode" for item in body["items"])

    body = client.get("/api/ai/users/u1/memories", params={"limit": 1}).json()
    assert body["total"] == 3  # total 是匹配总数，不受分页影响
    assert len(body["items"]) == 1


def test_list_user_memories_paginates_server_side():
    svc = _svc()
    for i in range(3):
        svc.add_episode("u1", f"事件{i}")
    client = _client(svc)

    page1 = client.get(
        "/api/ai/users/u1/memories", params={"page_size": 2, "page": 1}
    ).json()
    assert page1["total"] == 3
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert len(page1["items"]) == 2

    page2 = client.get(
        "/api/ai/users/u1/memories", params={"page_size": 2, "page": 2}
    ).json()
    assert page2["total"] == 3
    assert len(page2["items"]) == 1

    ids1 = {item["id"] for item in page1["items"]}
    ids2 = {item["id"] for item in page2["items"]}
    assert ids1.isdisjoint(ids2)
    assert ids1 | ids2 == {item["id"] for item in _client(svc).get(
        "/api/ai/users/u1/memories", params={"page_size": 10}
    ).json()["items"]}


def test_list_user_memories_sorts_by_importance():
    svc = _svc()
    svc.add_profile("u1", "画像（重要度 4）")  # importance=4
    svc.add_episode("u1", "事件（重要度 3）")  # importance=3
    client = _client(svc)

    asc = client.get(
        "/api/ai/users/u1/memories",
        params={"sort_by": "importance", "sort_order": "asc"},
    ).json()
    assert [item["importance"] for item in asc["items"]] == [3, 4]

    desc = client.get(
        "/api/ai/users/u1/memories",
        params={"sort_by": "importance", "sort_order": "desc"},
    ).json()
    assert [item["importance"] for item in desc["items"]] == [4, 3]


def test_list_user_memories_excludes_expired_episodes():
    svc = _svc()
    svc.add_from_extract(
        "u1",
        MemoryExtractItem(
            content="过期结论",
            memory_type=MemoryType.EPISODE,
            expires_at=datetime.utcnow() - timedelta(days=1),
        ),
    )
    svc.add_episode("u1", "有效结论")

    body = _client(svc).get(
        "/api/ai/users/u1/memories", params={"memory_type": "episode"}
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["content"] == "有效结论"


def test_list_user_memories_rejects_invalid_sort_field():
    resp = _client(_svc()).get(
        "/api/ai/users/u1/memories", params={"sort_by": "content"}
    )
    assert resp.status_code == 422


def test_long_memory_content_is_truncated():
    svc = _svc()
    svc.add_profile("u1", "长" * 500)

    body = _client(svc).get("/api/ai/users/u1/memories").json()
    item = body["items"][0]
    assert item["content_truncated"] is True
    assert len(item["content"]) == 201  # 200 字符 + 省略号
    assert item["content"].endswith("…")
