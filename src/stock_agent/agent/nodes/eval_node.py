
from eval.feedback import calculate_scores
from event.decorator import node
from loguru import logger
from shared.agents.agent_state import AgentState


@node(node_name="evaluation", title="基本面数据节点")
async def eval_node(state: AgentState) -> dict:
    """在 final_answer 产生后执行"""
    answer = state.get("final_answer") or ""
    contexts = state.get("rag_contexts") or []

    if not answer or not contexts:
        logger.error("no answer or contexts for feedback")
        return {
            "ragas_result": {
                "faithfulness": None,
                "reason": "missing answer or context"
            }
        }

    scores = await calculate_scores(state)

    return {
        "ragas_result": {
            **scores
        }
    }
