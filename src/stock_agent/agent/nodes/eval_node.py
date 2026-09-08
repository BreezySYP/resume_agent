
from eval.feedback import calculate_scores
from event.decorator import node
from loguru import logger
from shared.agents.agent_state import AgentState

_GROUNDING_FIELDS = (
    "stock_financial_factor",
    "stock_technique_factor",
    "stock_profile",
    "memory_context",
    "news_items",
)


def _has_grounding_evidence(state) -> bool:
    """五类 grounding 证据字段中任一非空即有证据。"""
    return any(bool(state.get(field)) for field in _GROUNDING_FIELDS)


@node(node_name="evaluation", title="评估节点")
async def eval_node(state: AgentState) -> dict:
    """在 final_answer 产生后执行"""
    answer = state.get("final_answer") or ""

    if not answer or not _has_grounding_evidence(state):
        logger.error("no answer or grounding evidence for feedback")
        return {
            "ragas_result": {
                "faithfulness": None,
                "reason": "missing answer or grounding evidence"
            }
        }

    scores = await calculate_scores(state)

    return {
        "ragas_result": {
            **scores
        }
    }
