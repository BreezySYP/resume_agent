"""news 节点（确定性检索 + 结构化输出）与 AgentState 字段声明测试。"""
from agent.nodes.news_node import (
    NewsAnalysisResult,
    _build_news_prompt,
    _dedup_news,
    _filter_news_items_by_cited,
    _search_stock_news,
    _strip_news_record,
)
from shared.agents.agent_state import AgentState


def test_agent_state_declares_news_items():
    assert "news_items" in AgentState.__annotations__
    assert "news_analysis_summary" in AgentState.__annotations__
    assert "news_cited_ids" in AgentState.__annotations__


def test_news_prompt_requires_per_sentence_citation():
    prompt = _build_news_prompt("2026-08-31", "能科科技 科远智慧", [{"name": "能科科技"}])
    assert "新闻id" in str(prompt.content)
    assert "引用 id 只能来自 search_news" in str(prompt.content)
    assert "content" in str(prompt.content)
    assert "cited_news_ids" in str(prompt.content)
    assert "不得编造新闻" in str(prompt.content)
    assert "不要输出任何思考过程、解释或前言" in str(prompt.content)


def test_news_analysis_result_missing_cited_ids_defaults_to_empty():
    result = NewsAnalysisResult.model_validate({"content": "正文【新闻id: 1001】。"})
    assert result.cited_news_ids == []


def test_search_stock_news_returns_docs_or_empty(monkeypatch):
    docs = [{"id": 1, "code": "600001", "title": "A"}]
    monkeypatch.setattr(
        "agent.nodes.news_node.search_news",
        type("Tool", (), {"invoke": lambda self, kwargs: docs})(),
    )
    assert _search_stock_news("公司600001") == docs

    def boom(kwargs):
        raise RuntimeError("search down")

    monkeypatch.setattr(
        "agent.nodes.news_node.search_news",
        type("Tool", (), {"invoke": boom})(),
    )
    assert _search_stock_news("公司600001") == []


def test_strip_and_dedup_news_records():
    records = [
        {"id": 1, "code": "600001", "title": "A", "embedding": "[0.1]"},
        {"id": 1, "code": "600001", "title": "A", "embedding": "[0.1]"},
        {"id": 2, "code": "600002", "title": "B"},
    ]
    deduped = _dedup_news(records)
    assert [r["id"] for r in deduped] == [1, 2]
    stripped = _strip_news_record(records[0])
    assert stripped == {"id": 1, "code": "600001", "title": "A"}


def test_filter_news_items_by_cited():
    records = [{"id": 1001, "title": "A"}, {"id": 1002, "title": "B"}, {"id": 1003, "title": "C"}]
    assert _filter_news_items_by_cited(records, [1002]) == [records[1]]
    assert _filter_news_items_by_cited(records, [1001, 1003]) == [records[0], records[2]]
    assert _filter_news_items_by_cited(records, [9999]) == []
    assert _filter_news_items_by_cited(records, []) == records
