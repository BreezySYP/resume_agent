"""faithfulness REST API 单测（不触发外部服务）。"""
from api import eval_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from observe.metrics import EVAL_RUNS
from shared.auth.deps import get_current_user
from shared.auth.errors import add_auth_exception_handlers

ADMIN_USER = {
    "id": "admin",
    "email": "admin@example.com",
    "name": "admin",
    "avatar_url": None,
    "is_admin": True,
}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(eval_router.router)
    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
    add_auth_exception_handlers(app)
    return TestClient(app)


def test_faithfulness_endpoint_requires_admin():
    app = FastAPI()
    app.include_router(eval_router.router)
    app.dependency_overrides[get_current_user] = lambda: {
        **ADMIN_USER,
        "is_admin": False,
    }
    add_auth_exception_handlers(app)
    resp = TestClient(app).post(
        "/api/ai/faithfulness",
        json={"answer": "a", "question": "q", "rag_context": []},
    )
    assert resp.status_code == 403


def test_faithfulness_endpoint(monkeypatch):
    captured = {}

    async def fake_score(answer, question, rag_context):
        captured.update(answer=answer, question=question, rag_context=rag_context)
        return 0.5, [
            {
                "claim": "能科科技（603859）财务总分0.54。",
                "supported": 1.0,
                "evidence": ["[603859] total_score: 0.54"],
            }
        ]

    monkeypatch.setattr(eval_router, "caculate_faithfulness_score", fake_score)

    resp = _client().post(
        "/api/ai/faithfulness",
        json={
            "answer": "A（600001）有增长。",
            "question": "q",
            "rag_context": [{"source": "profile", "code": "600001"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["faithfulness"] == 0.5
    assert body["faithfulness_claims"] == [
        {
            "claim": "能科科技（603859）财务总分0.54。",
            "sentences": ["[603859] total_score: 0.54"],
            "result": "完全支持",
        }
    ]
    assert captured["answer"] == "A（600001）有增长。"
    assert captured["rag_context"] == [{"source": "profile", "code": "600001"}]


def test_faithfulness_endpoint_counts_eval_runs(monkeypatch):
    async def fake_score(answer, question, rag_context):
        return 0.5, []

    monkeypatch.setattr(eval_router, "caculate_faithfulness_score", fake_score)
    before = EVAL_RUNS.labels(status="ok")._value.get()
    resp = _client().post(
        "/api/ai/faithfulness",
        json={"answer": "a", "question": "q", "rag_context": []},
    )
    assert resp.status_code == 200
    assert EVAL_RUNS.labels(status="ok")._value.get() == before + 1


def test_faithfulness_endpoint_counts_error_runs(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(eval_router, "caculate_faithfulness_score", boom)
    before = EVAL_RUNS.labels(status="error")._value.get()
    resp = _client().post(
        "/api/ai/faithfulness",
        json={"answer": "a", "question": "q", "rag_context": []},
    )
    assert resp.status_code == 500
    assert EVAL_RUNS.labels(status="error")._value.get() == before + 1


def test_faithfulness_endpoint_missing_required_fields():
    resp = _client().post("/api/ai/faithfulness", json={"answer": "x"})
    assert resp.status_code == 422


def test_faithfulness_endpoint_returns_500_on_failure(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(eval_router, "caculate_faithfulness_score", boom)
    resp = _client().post(
        "/api/ai/faithfulness",
        json={"answer": "a", "question": "q", "rag_context": []},
    )
    assert resp.status_code == 500
    assert "llm down" in resp.json()["detail"]
