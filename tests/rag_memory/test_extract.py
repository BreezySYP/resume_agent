"""rag_memory.extract 提示词模板测试。"""
from rag_memory.extract import build_extract_prompt
from rag_memory.schemas import MemoryTier


def test_prompt_contains_default_tiers_and_fields():
    prompt = build_extract_prompt(
        user_question="贵州茅台值得买吗",
        conversation_summary="结论：基本面稳健",
    )
    assert "episodic: 本轮交互的高密度摘要" in prompt
    assert "semantic: 用户的长期事实" in prompt
    assert "procedural: 可复用的分析经验" in prompt
    assert "## 用户问题\n贵州茅台值得买吗" in prompt
    assert "## 本轮内容（可截断）\n结论：基本面稳健" in prompt


def test_prompt_custom_tiers_and_extra_guidance():
    prompt = build_extract_prompt(
        tiers=(MemoryTier.CONSOLIDATED,),
        extra_guidance="不要保存原始行情",
    )
    assert "consolidated: 对若干轮次提炼后的中期结论" in prompt
    assert "不要保存原始行情" in prompt
    assert "semantic:" not in prompt


def test_prompt_empty_fields_fall_back_to_placeholders():
    prompt = build_extract_prompt()
    assert "（无）" in prompt
