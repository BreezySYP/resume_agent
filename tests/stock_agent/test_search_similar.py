"""search_with_rerank 的 rerank 降级与排序逻辑单测（不依赖外部服务）。"""
import pandas as pd
from service import search_similar


def _fake_results():
    return pd.DataFrame(
        [
            {"id": 1, "code": "600001", "original_score": 0.2},
            {"id": 2, "code": "600002", "original_score": 0.9},
            {"id": 3, "code": "600003", "original_score": 0.5},
        ]
    )


def test_search_with_rerank_falls_back_to_original_score(monkeypatch):
    def fail_rerank(query, docs, timeout=30):
        raise TimeoutError("rerank timeout")

    monkeypatch.setattr(search_similar, "rerank", fail_rerank)
    monkeypatch.setattr(search_similar, "search_hybrid_join", lambda *a, **k: _fake_results())

    result = search_similar.search_with_rerank(
        "q", "c", "t", lambda row: "text", top_k=2
    )
    assert result["code"].tolist() == ["600002", "600003"]


def test_search_with_rerank_uses_rerank_score(monkeypatch):
    def fake_rerank(query, docs, timeout=30):
        return pd.DataFrame({"rerank_score": [0.9, 0.1, 0.5], "docs": ["a", "b", "c"]})

    monkeypatch.setattr(search_similar, "rerank", fake_rerank)
    monkeypatch.setattr(search_similar, "search_hybrid_join", lambda *a, **k: _fake_results())

    result = search_similar.search_with_rerank(
        "q", "c", "t", lambda row: "text", top_k=2
    )
    assert result["code"].tolist() == ["600001", "600003"]


def test_search_with_rerank_caps_rerank_input(monkeypatch):
    big = pd.DataFrame(
        [
            {"id": i, "code": f"60{i:04d}", "original_score": float(1000 - i)}
            for i in range(1, 80)
        ]
    )
    captured = {}

    def fake_rerank(query, docs, timeout=30):
        captured["docs"] = docs
        return pd.DataFrame(
            {"rerank_score": [float(len(docs) - j) for j in range(len(docs))], "docs": docs}
        )

    monkeypatch.setattr(search_similar, "rerank", fake_rerank)
    monkeypatch.setattr(search_similar, "search_hybrid_join", lambda *a, **k: big)

    result = search_similar.search_with_rerank(
        "q", "c", "t", lambda row: "text", top_k=3, rerank_cap=50
    )
    assert len(captured["docs"]) == 50
    assert len(result) == 3
