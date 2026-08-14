# agent/nodes/memory_write_node.py
from event.decorator import node
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from memory.mem_service import MemoryService
from memory.models import MemoryExtractResult
from rag_memory.extract import build_extract_prompt
from shared.agents.agent_state import AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek

_memory_svc = MemoryService(use_hybrid=True)


@node(node_name="memory_write", title="记忆写入节点")
def memory_write_node(state: AgentState) -> dict:
    user_id = state.get("user_id") or state.get("thread_id") or "anonymous"
    question = state.get("user_question") or ""
    final_answer = state.get("final_answer") or ""
    reflections = state.get("reflections") or []
    reflection_text = reflections[-1] if reflections else ""

    thread_id = state.get("thread_id")
    job_id = str(state.get("job_id") or "")

    EXTRACT_PROMPT = build_extract_prompt(
        user_question=question,
        conversation_summary=f"""## 最终结论（可截断）
        {final_answer[:3000]}

        ## Reflection
        {reflection_text[:1500]}
        """,
        extra_guidance="""
        领域说明：
        - profile: 用户投资偏好、风险承受、约束（如“只看成长股”）
        - episode: 本轮问题与核心结论的高密度摘要（一两句）
        - procedural: 可复用分析教训（如“新闻强但技术超买需强调回撤”）
        """,
    )

    try:
        llm_name = "deepseek-chat"
        llm = get_deepseek(llm_name)  # 你的 chat model
        extractor = llm.with_structured_output(MemoryExtractResult)

        result: MemoryExtractResult = invoke_with_metrics(
            extractor,
            [
                SystemMessage(content=EXTRACT_PROMPT),
                HumanMessage(content=question),
            ],
            "memory_write",
            llm_name,
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
        saved = _memory_svc.add_from_extract_batch(
            user_id=user_id, items=items)
        logger.info("memory write user={} count={}", user_id, len(saved))
    except Exception as e:
        logger.exception("memory write failed: {}", e)

    return {}  # 不强制改业务状态
