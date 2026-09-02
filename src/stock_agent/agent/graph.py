"""src/stock_agent/agent/graph.py"""


from agent.nodes.eval_node import eval_node
from agent.nodes.fundamental_node import fundamental_node
from agent.nodes.memory_recall_node import memory_recall_node
from agent.nodes.memory_write_node import memory_write_node
from agent.nodes.news_node import news_node
from agent.nodes.profile_node import profile_node
from agent.nodes.reflection_node import reflection_node

# 导入所有 node 函数
from agent.nodes.supervisor_node import supervisor_node
from agent.nodes.synthesizer_node import synthesizer_node
from agent.nodes.technical_node import technical_node
from agent.routing import should_continue
from event.event_manager import event
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from shared.agents.agent_state import AgentState
from shared.agents.checkpoint import get_aredis_checkpointer


def build_investment_agent(checkpointer):
    """生产级 Graph 构建函数"""
    workflow = StateGraph(AgentState)
    
    # 统一 retry 配置
    default_retry = RetryPolicy(max_attempts=3, retry_on=[Exception])  # 可自定义异常
    
    workflow.add_node("supervisor", supervisor_node, retry_policy=default_retry)
    workflow.add_node("profile", profile_node, retry_policy=default_retry)
    workflow.add_node("fundamental", fundamental_node, retry_policy=default_retry)
    workflow.add_node("technical", technical_node, retry_policy=default_retry)
    workflow.add_node("news", news_node, retry_policy=default_retry)
    workflow.add_node("synthesizer", synthesizer_node, retry_policy=default_retry)
    workflow.add_node("reflection", reflection_node, retry_policy=default_retry)
    workflow.add_node("eval", eval_node, retry_policy=default_retry)
    workflow.add_node("memory_write", memory_write_node, retry_policy=default_retry)
    workflow.add_node("memory_recall", memory_recall_node, retry_policy=default_retry)

    
    # 边（并行结构清晰）
    workflow.add_edge(START, "memory_recall")
    workflow.add_edge("memory_recall", "supervisor")
    workflow.add_edge("supervisor", "profile")
    
    workflow.add_edge("profile", "fundamental")
    workflow.add_edge("profile", "technical")
    workflow.add_edge("profile", "news")
    
    workflow.add_edge("fundamental", "synthesizer")
    workflow.add_edge("technical", "synthesizer")
    workflow.add_edge("news", "synthesizer")

    workflow.add_edge("synthesizer", "reflection")
    workflow.add_edge("memory_write", "eval")
    workflow.add_edge("eval", END)

    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "synthesizer": "synthesizer",
            "memory_write": "memory_write" 
        }
    )

    return workflow.compile(
        checkpointer=checkpointer
    )


async def ask_investment(question: str, job_id: str, thread_id: str = "default"):
    """推荐入口"""
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,          # 防止无限循环
    }
    
    async with get_aredis_checkpointer() as cp:
        cp.setup()
        agent = build_investment_agent(checkpointer=cp)
        result = await agent.ainvoke({"user_question": question, "thread_id": thread_id, "job_id": job_id}, config=config)

    
    event.graph_finish(job_id, "END", result.get("final_answer", "获取最终答案失败，请查询日志"))
    
    return result


