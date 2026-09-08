"""对话历史 API：build_conversation 与 GET/DELETE 端点单测（不触发外部服务）。"""
from api import conversation_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, SystemMessage


def test_build_conversation_from_messages_only():
    state = {
        "user_question": "白酒板块怎么看",
        "plan": {"plan_summary": "不应出现在对话里"},
        "reflections": ["也不应出现"],
        "messages": [
            "白酒板块怎么看",
            SystemMessage(content="报告一"),
            SystemMessage(content="报告二"),
        ],
        "final_answer": "报告二",
    }
    result = conversation_router.build_conversation(state)
    assert [(item["role"], item["type"]) for item in result["items"]] == [
        ("user", "user_question"),
        ("agent", "report"),
        ("agent", "report"),
    ]
    assert result["items"][0]["content"] == "白酒板块怎么看"
    assert result["items"][1]["content"] == "报告一"
    assert result["items"][2]["content"] == "报告二"
    assert result["final_answer"] == "报告二"


def test_build_conversation_minimal_state():
    result = conversation_router.build_conversation({})
    assert result["items"] == []
    assert result["final_answer"] is None


def test_build_conversation_user_from_string_and_human_message():
    result = conversation_router.build_conversation(
        {"messages": ["字符串问题", HumanMessage(content="消息对象问题"), SystemMessage(content="报告")]}
    )
    assert [(item["role"], item["content"]) for item in result["items"]] == [
        ("user", "字符串问题"),
        ("user", "消息对象问题"),
        ("agent", "报告"),
    ]


def test_build_conversation_skips_empty_messages():
    result = conversation_router.build_conversation(
        {"messages": [SystemMessage(content=""), SystemMessage(content="有内容")]}
    )
    agent_items = [item for item in result["items"] if item["role"] == "agent"]
    assert len(agent_items) == 1
    assert agent_items[0]["content"] == "有内容"


class _FakeSnapshot:
    def __init__(self, values):
        self.checkpoint = {"channel_values": values}


class _FakeCP:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.deleted: list[str] = []

    async def aget_tuple(self, config):
        return self._snapshot

    async def adelete_thread(self, thread_id):
        self.deleted.append(thread_id)


class _BoomCP:
    async def aget_tuple(self, config):
        raise RuntimeError("redis down")

    async def adelete_thread(self, thread_id):
        raise AssertionError("adelete_thread 不应在 Redis 不可用时被调用")


def _patch_shared_cp(monkeypatch, cp):
    async def _get():
        return cp

    monkeypatch.setattr(conversation_router, "get_shared_aredis_checkpointer", _get)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(conversation_router.router)
    return TestClient(app)


def test_get_conversation_200(monkeypatch):
    state = {
        "user_question": "q",
        "final_answer": "a",
        "job_id": "j-1",
        "current_time": "2026-09-02",
        "messages": ["q", SystemMessage(content="a")],
    }
    cp = _FakeCP(_FakeSnapshot(state))
    _patch_shared_cp(monkeypatch, cp)
    resp = _client().get("/api/ai/threads/t1/conversation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == "t1"
    assert body["job_id"] == "j-1"
    assert body["final_answer"] == "a"
    assert [(item["role"], item["type"]) for item in body["items"]] == [
        ("user", "user_question"),
        ("agent", "report"),
    ]


def test_get_conversation_404(monkeypatch):
    _patch_shared_cp(monkeypatch, _FakeCP(None))
    resp = _client().get("/api/ai/threads/nope/conversation")
    assert resp.status_code == 404


def test_delete_conversation_200(monkeypatch):
    cp = _FakeCP(_FakeSnapshot({"messages": []}))
    _patch_shared_cp(monkeypatch, cp)
    resp = _client().delete("/api/ai/threads/t1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "thread_id": "t1"}
    assert cp.deleted == ["t1"]


def test_delete_conversation_404(monkeypatch):
    cp = _FakeCP(None)
    _patch_shared_cp(monkeypatch, cp)
    resp = _client().delete("/api/ai/threads/nope")
    assert resp.status_code == 404
    assert cp.deleted == []


def test_get_conversation_503_when_redis_down(monkeypatch):
    _patch_shared_cp(monkeypatch, _BoomCP())
    resp = _client().get("/api/ai/threads/t1/conversation")
    assert resp.status_code == 503
    assert "Redis" in resp.json()["detail"]


def test_delete_conversation_503_when_redis_down(monkeypatch):
    _patch_shared_cp(monkeypatch, _BoomCP())
    resp = _client().delete("/api/ai/threads/t1")
    assert resp.status_code == 503
