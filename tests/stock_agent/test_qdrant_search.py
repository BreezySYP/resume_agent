"""stock_agent/service/qdrant_search 的 chunk 聚合逻辑测试。"""
import pandas as pd
from service.qdrant_search import _aggregate_by_group_key, search_dense


def test_aggregate_by_group_key_dedupes_chunks_and_falls_back_for_old_points():
    hits = pd.DataFrame(
        [
            {"id": "u1", "score": 0.9, "payload": {"article_id": "2", "chunk_index": 0}},
            {"id": "u2", "score": 0.85, "payload": {"article_id": "2", "chunk_index": 1}},
            {"id": "u3", "score": 0.8, "payload": {"article_id": "3", "chunk_index": 0}},
            {"id": 1, "score": 0.7, "payload": {"code": "600000", "title": "old style"}},
        ]
    )
    out = _aggregate_by_group_key(hits, "article_id")
    assert list(out["id"]) == ["2", "3", "1"]
    assert out.iloc[0]["score"] == 0.9


def test_aggregate_by_group_key_empty():
    assert _aggregate_by_group_key(pd.DataFrame(), "article_id").empty


def test_search_dense_group_key_scales_limit_and_aggregates(monkeypatch):
    class FakeResp:
        def model_dump(self):
            return {
                "points": [
                    {"id": "u1", "score": 0.9, "payload": {"article_id": "2", "chunk_index": 0}},
                    {"id": "u2", "score": 0.8, "payload": {"article_id": "2", "chunk_index": 1}},
                    {"id": 1, "score": 0.7, "payload": {"code": "x"}},
                ]
            }

    class FakeClient:
        def __init__(self):
            self.kwargs = None

        def query_points(self, **kwargs):
            self.kwargs = kwargs
            return FakeResp()

    fake = FakeClient()
    monkeypatch.setattr("service.qdrant_search.get_qdrant_client", lambda: fake)
    monkeypatch.setattr(
        "service.qdrant_search.get_embedding",
        lambda: type("E", (), {"embed_query": lambda self, q: [0.0] * 4})(),
    )

    out = search_dense("col", "q", top_k=5, group_key="article_id")
    assert fake.kwargs["limit"] == 20
    assert list(out["id"]) == ["2", "1"]
