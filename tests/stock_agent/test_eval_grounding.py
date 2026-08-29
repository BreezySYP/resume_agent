"""faithfulness 证据组装 与 eval 早退判断 的单测（不依赖外部服务）。"""
import agent.nodes.eval_node as en
from eval.faithfulness import _build_grounding_context


def test_grounding_context_orders_and_cleans_fields():
    state = {
        "stock_financial_factor": [
            {
                "code": "600001",
                "name": "公司600001",
                "profitability_score": 0.72,
                "total_financial_score": 0.54,
            }
        ],
        "stock_technique_factor": [{"code": "600001", "trend_score": 0.81}],
        "stock_profile": [{"code": "600001", "name": "公司600001", "business": "工业软件"}],
        "memory_context": "用户偏好稳健",
        "news_items": [
            "<em>新闻</em>标题：公司发布中报。\\u3000净利增长。",
            "Tool search_news called with {'query': '公司'}",
        ],
    }

    parts = _build_grounding_context(state).split("\n\n")

    assert parts[0] == (
        "公司600001（600001）\n"
        "profitability_score: 0.72\n"
        "total_financial_score: 0.54"
    )
    assert parts[1] == "trend_score: 0.81"
    assert parts[2] == "公司600001（600001）\n工业软件"
    assert parts[3] == "用户偏好稳健"
    assert parts[4] == "新闻标题：公司发布中报。 净利增长。"


def test_grounding_context_skips_empty_and_placeholder():
    state = {
        "memory_context": "（暂无相关长期记忆）",
        "news_items": [],
        "stock_profile": [],
        "stock_technique_factor": [],
    }
    assert _build_grounding_context(state) == ""

    state["stock_financial_factor"] = [{"code": "600001", "profitability_score": 0.5}]
    assert _build_grounding_context(state) == "profitability_score: 0.5"


def test_grounding_context_all_empty():
    assert _build_grounding_context({}) == ""


def test_has_grounding_evidence():
    assert en._has_grounding_evidence({}) is False
    assert en._has_grounding_evidence({"news_items": [], "stock_profile": []}) is False
    assert en._has_grounding_evidence({"memory_context": "x"}) is True
    assert en._has_grounding_evidence({"stock_profile": [{}]}) is True
    assert en._has_grounding_evidence({"news_items": ["新闻"]}) is True
