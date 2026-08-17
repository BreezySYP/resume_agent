"""LLM 记忆提取提示词模板（结构化输出）。"""
from __future__ import annotations

from rag_memory.schemas import MemoryTier

TIER_GUIDANCE: dict[MemoryTier, str] = {
    MemoryTier.EPISODIC: "episodic: 本轮交互的高密度摘要（一两句，可过期）",
    MemoryTier.CONSOLIDATED: "consolidated: 对若干轮次提炼后的中期结论",
    MemoryTier.SEMANTIC: "semantic: 用户的长期事实、偏好、约束（不可过期）",
    MemoryTier.PROCEDURAL: "procedural: 可复用的分析经验、教训、方法论",
}


def build_extract_prompt(
    *,
    user_question: str = "",
    conversation_summary: str = "",
    tiers: tuple[MemoryTier, ...] = (MemoryTier.EPISODIC, MemoryTier.SEMANTIC, MemoryTier.PROCEDURAL),
    extra_guidance: str = "",
) -> str:
    """构建记忆提取 System 提示词。

    只提取对未来真正有用的内容；没有则返回空 items。
    类别说明由 tiers 决定；extra_guidance 可追加领域规则（如"不要保存原始行情"）。
    """
    tier_lines = "\n".join(
        f"- {TIER_GUIDANCE[t]}" for t in tiers if t in TIER_GUIDANCE
    )
    return f"""你是记忆提取器。根据本轮交互，提取值得跨会话保存的记忆。
        只输出真正对未来有用的内容；没有则 items 为空列表。

        类别说明：
        {tier_lines}

        {extra_guidance}

        不要保存：原始行情、完整长报告、一次性中间推理。

        ## 用户问题
        {user_question or "（无）"}

        ## 本轮内容（可截断）
        {conversation_summary or "（无）"}
        """
