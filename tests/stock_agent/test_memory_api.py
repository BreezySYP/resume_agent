"""stock_agent memory list API 测试（注入 InMemory 存储，不依赖 MySQL/Qdrant）。"""
from api.memory_router import _memory_service, router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from memory.mem_service import MemoryService
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
    assert body["total"] == 1


def test_long_memory_content_is_truncated():
    svc = _svc()
    svc.add_profile("u1", "长" * 500)

    body = _client(svc).get("/api/ai/users/u1/memories").json()
    item = body["items"][0]
    assert item["content_truncated"] is True
    assert len(item["content"]) == 201  # 200 字符 + 省略号
    assert item["content"].endswith("…")
