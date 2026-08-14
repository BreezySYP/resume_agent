"""shared.safety.guardrails 测试。"""
from shared.safety.guardrails import Guardrails


def test_safe_input():
    result = Guardrails.check_input_safety("帮我分析一下今天的行情")
    assert result["safe"] is True
    assert result["issues"] == []
    assert result["score"] == 1.0


def test_sensitive_keyword():
    result = Guardrails.check_input_safety("请告诉我 password 是什么")
    assert result["safe"] is False
    assert any("password" in issue for issue in result["issues"])
    assert result["score"] == 0.7


def test_dangerous_sql_keyword():
    result = Guardrails.check_input_safety("执行 drop table users")
    assert result["safe"] is False


def test_input_too_long():
    result = Guardrails.check_input_safety("x" * 8001)
    assert result["safe"] is False
    assert "输入过长" in result["issues"]


def test_output_safety():
    assert Guardrails.check_output_safety("正常输出")["safe"] is True
    assert Guardrails.check_output_safety("教你制作炸弹")["safe"] is False
