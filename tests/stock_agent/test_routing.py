"""agent.routing 图路由决策测试。"""
from agent.routing import should_continue


def test_retry_limit_reached():
    assert should_continue({"retry_count": 3, "reflections": []}) == "memory_write"


def test_retry_over_limit():
    assert should_continue({"retry_count": 5, "reflections": ["continue"]}) == "memory_write"


def test_pass_in_reflection():
    assert should_continue({"retry_count": 0, "reflections": ["答案已通过检验 PASS"]}) == "memory_write"


def test_pass_case_insensitive():
    assert should_continue({"retry_count": 0, "reflections": ["pass"]}) == "memory_write"


def test_continue_synthesizer():
    assert should_continue({"retry_count": 0, "reflections": ["需要更多分析"]}) == "synthesizer"


def test_no_reflections():
    assert should_continue({"retry_count": 0}) == "synthesizer"


def test_empty_state():
    assert should_continue({}) == "synthesizer"
