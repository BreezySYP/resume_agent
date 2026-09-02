"""对话历史 API：build_conversation 与端点单测（不触发外部服务）。"""
from api import conversation_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import SystemMessage


def test_build_conversation_full_state():
    state = {
        "user_question": "白酒板块怎么看",
        "plan": {"plan_summary": "分析白酒", "focus_areas": ["news"]},
        "news_analysis": "白酒处于筑底期【新闻id: 1】",
        "messages": [
            "白酒板块怎么看",
            SystemMessage(content="报告一"),
            SystemMessage(content="报告二"),
        ],
        "reflections": ["建议补充风险", "PASS"],
        "final_answer": "报告二",
    }
    result = conversation_router.build_conversation(state)
    roles_types = [(item["role"], item["type"]) for item in result["items"]]
    assert roles_types == [
        ("user", "user_question"),
        ("reasoning", "plan"),
        ("reasoning", "news_analysis"),
        ("agent", "report"),
        ("agent", "report"),
        ("reasoning", "reflection"),
        ("reasoning", "reflection"),
    ]
    assert result["items"][0]["content"] == "白酒板块怎么看"
    assert "plan_summary" in result["items"][1]["content"]
    assert result["items"][3]["content"] == "报告一"
    assert result["items"][4]["content"] == "报告二"
    assert result["final_answer"] == "报告二"


def test_build_conversation_minimal_state():
    result = conversation_router.build_conversation({})
    assert result["items"] == []
    assert result["final_answer"] is None


def test_build_conversation_user_question_fallback():
    state = {
        "messages": ["用户问题", SystemMessage(content="报告")],
        "final_answer": "报告",
    }
    result = conversation_router.build_conversation(state)
    assert result["items"][0] == {
        "role": "user",
        "type": "user_question",
        "content": "用户问题",
    }
    assert result["items"][1]["role"] == "agent"


def test_build_conversation_skips_empty_messages():
    state = {
        "user_question": "q",
        "messages": [SystemMessage(content=""), SystemMessage(content="有内容")],
    }
    result = conversation_router.build_conversation(state)
    agent_items = [item for item in result["items"] if item["role"] == "agent"]
    assert len(agent_items) == 1
    assert agent_items[0]["content"] == "有内容"


class _FakeSnapshot:
    def __init__(self, values):
        self.checkpoint = {"channel_values": values}


class _FakeCP:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    async def aget_tuple(self, config):
        return self._snapshot


class _FakeCM:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    async def __aenter__(self):
        return _FakeCP(self._snapshot)

    async def __aexit__(self, *args):
        return None


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
    }
    monkeypatch.setattr(
        conversation_router, "get_aredis_checkpointer", lambda: _FakeCM(_FakeSnapshot(state))
    )
    resp = _client().get("/api/ai/threads/t1/conversation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == "t1"
    assert body["job_id"] == "j-1"
    assert body["current_time"] == "2026-09-02"
    assert body["final_answer"] == "a"
    assert body["items"][0]["role"] == "user"


def test_get_conversation_404(monkeypatch):
    monkeypatch.setattr(
        conversation_router, "get_aredis_checkpointer", lambda: _FakeCM(None)
    )
    resp = _client().get("/api/ai/threads/nope/conversation")
    assert resp.status_code == 404
    assert "thread not found" in resp.json()["detail"]
