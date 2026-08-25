"""push_to_langsmith 测试：同一 job_id 重复调用必须使用独立 run id，失败不抛出。"""
from shared.rag.eval import push_to_langsmith


class _FakeClient:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.updated: list[tuple] = []
        self.feedbacks: list[dict] = []

    def create_run(self, **kwargs):
        self.created.append(kwargs)
        return type("Run", (), {"id": kwargs["id"]})()

    def update_run(self, *args, **kwargs):
        self.updated.append((args, kwargs))

    def create_feedback(self, **kwargs):
        self.feedbacks.append(kwargs)


def test_same_job_id_uses_distinct_run_ids(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("shared.rag.eval._ls_client", fake)
    scores = {
        "faithfulness": 0.8,
        "answer_relevancy": 0.9,
        "timestamp": "2026-01-01 00:00:00",
    }

    push_to_langsmith(scores, "q1", "a1", "job-1")
    push_to_langsmith(scores, "q1", "a1", "job-1")

    assert len(fake.created) == 2
    assert fake.created[0]["id"] != fake.created[1]["id"], "同一 job_id 不应复用 LangSmith run id"
    for created in fake.created:
        assert created["metadata"] == {"job_id": "job-1"}
    # 每次调用都更新各自独立的 run，不会出现对同一 run 的重复 update
    assert len(fake.updated) == 2
    assert fake.updated[0][0][0] != fake.updated[1][0][0]
    assert len(fake.feedbacks) == 4


def test_push_failure_is_non_fatal(monkeypatch):
    class _BoomClient(_FakeClient):
        def create_run(self, **kwargs):
            raise RuntimeError("langsmith down")

    monkeypatch.setattr("shared.rag.eval._ls_client", _BoomClient())

    # 推送失败只记 warning，不应抛出
    push_to_langsmith(
        {"faithfulness": 1.0, "timestamp": "2026-01-01 00:00:00"},
        "q",
        "a",
        "job-2",
    )
