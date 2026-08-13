# agent/nodes/memory_write_node.py
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage

from memory.mem_service import MemoryService
from memory.models import MemoryExtractResult
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek

_memory_svc = MemoryService(use_hybrid=True)

EXTRACT_PROMPT = """你是记忆提取器。根据本轮投资分析交互，提取值得跨会话保存的记忆。
只输出真正对未来有用的内容；没有则 items 为空列表。

类别说明：
- profile: 用户投资偏好、风险承受、约束（如“只看成长股”）
- episode: 本轮问题与核心结论的高密度摘要（一两句）
- procedural: 可复用分析教训（如“新闻强但技术超买需强调回撤”）

不要保存：原始行情、完整长报告、一次性中间推理。
"""


def memory_write_node(state: AgentState) -> dict:
    user_id = state.get("user_id") or state.get("thread_id") or "anonymous"
    question = state.get("user_question") or ""
    final_answer = state.get("final_answer") or ""
    reflections = state.get("reflections") or []
    reflection_text = reflections[-1] if reflections else ""

    thread_id = state.get("thread_id")
    job_id = str(state.get("job_id") or "")

    payload = f"""## 用户问题
        {question}

        ## 最终结论（可截断）
        {final_answer[:3000]}

        ## Reflection
        {reflection_text[:1500]}
        """

    try:
        llm_name = "deepseek-chat"
        llm = get_deepseek(llm_name)  # 你的 chat model
        extractor = llm.with_structured_output(MemoryExtractResult)
        
        result: MemoryExtractResult = extractor.invoke(
            [
                SystemMessage(content=EXTRACT_PROMPT),
                HumanMessage(content=payload),
            ]
        )
        # 补齐来源会话信息
        items = []
        for it in result.items or []:
            items.append(
                it.model_copy(
                    update={
                        "source_thread_id": thread_id,
                        "source_job_id": job_id,
                    }
                )
            )
        saved = _memory_svc.add_from_extract_batch(user_id=user_id, items=items)
        logger.info("memory write user={} count={}", user_id, len(saved))
    except Exception as e:
        logger.exception("memory write failed: {}", e)

    return {}  # 不强制改业务状态