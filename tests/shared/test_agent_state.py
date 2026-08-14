"""shared.agents.agent_state 的 reducer 逻辑测试。"""
from shared.agents.agent_state import CLEAR_MARK, clear_list


def test_append_without_mark():
    assert clear_list(["a"], ["b", "c"]) == ["a", "b", "c"]


def test_clear_mark_resets_content():
    assert clear_list(["a", "b"], [CLEAR_MARK, "c"]) == ["c"]


def test_clear_mark_only():
    assert clear_list(["a"], [CLEAR_MARK]) == []


def test_empty_left():
    assert clear_list([], ["x"]) == ["x"]


def test_both_empty():
    assert clear_list([], []) == []
