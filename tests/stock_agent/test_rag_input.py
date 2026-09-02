"""rag_input：AgentState 解析与引用代码提取的单测。"""
from eval.rag_input import extract_cited_codes, retrieved_codes, state_to_rag_context


def test_state_to_rag_context_tags_sources():
    state = {
        "stock_profile": [{"code": "600001", "business": "工业软件"}],
        "stock_technique_factor": [{"code": "600001", "trend_score": 0.8}],
        "stock_financial_factor": [{"code": "600001", "profitability_score": 0.7}],
        "news_items": [{"id": 1, "title": "标题", "content": "正文"}],
        "memory_context": "用户偏好稳健",
    }
    rag = state_to_rag_context(state)
    sources = [r.get("source") for r in rag]
    assert sources == ["profile", "technical", "financial", "news", "memory"]
    assert rag[-1] == {"source": "memory", "memory": "用户偏好稳健"}


def test_state_to_rag_context_does_not_mutate_state():
    state = {"stock_profile": [{"code": "600001"}], "news_items": [], "memory_context": ""}
    state_to_rag_context(state)
    assert "source" not in state["stock_profile"][0]


def test_retrieved_codes_only_profile_records():
    rag = [
        {"source": "profile", "code": "600001"},
        {"code": "600002", "business": "工业软件"},
        {"source": "technical", "code": "600003"},
        {"source": "news", "code": "600004"},
    ]
    assert retrieved_codes(rag) == ["600001", "600002"]
    assert retrieved_codes([]) == []


def test_extract_cited_codes_filters_by_universe():
    answer = "推荐能科科技（603859）与 002380。营收增长5.1%。"
    assert extract_cited_codes(answer, {"603859", "002380", "999999"}) == {"603859", "002380"}
    assert extract_cited_codes(answer, {"603859"}) == {"603859"}
    assert extract_cited_codes("", {"603859"}) == set()
