# agent/nodes/memory_recall_node.py
from event.decorator import node
from loguru import logger
from memory.mem_service import MemoryService
from shared.agents.agent_state import AgentState

_memory_svc = MemoryService(use_hybrid=True)


@node(node_name="memory_recall", title="记忆回调节点")
def memory_recall_node(state: AgentState) -> dict:
    user_id = state.get("user_id") or state.get("thread_id") or "anonymous"
    question = state.get("user_question") or ""

    try:
        ctx = _memory_svc.search_for_prompt(
            user_id=user_id,
            query=question,
            limit=5,
        )
    except Exception as e:
        logger.warning("memory recall failed: {}", e)
        ctx = "（记忆检索失败，本轮不使用历史记忆）"

    return {"memory_context": ctx}