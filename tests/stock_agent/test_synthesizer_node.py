"""synthesizer prompt 构造的单测（不依赖外部服务）。"""
from agent.nodes.synthesizer_node import _build_synthesizer_prompt


def test_synthesizer_prompt_contains_news_analysis_and_no_id_instruction():
    state = {
        "news_analysis": "存储板块暴跌【新闻id: 386517】。",
        "user_question": "存储芯片还有机会吗",
        "stock_technique_factor": [],
        "stock_financial_factor": [],
        "memory_context": "",
    }
    prompt = _build_synthesizer_prompt(state)
    assert "存储板块暴跌【新闻id: 386517】" in prompt
    assert "禁止出现【新闻id】标注或任何新闻 id" in prompt
    assert "JSON Schema" in prompt
