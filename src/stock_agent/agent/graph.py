"""src/stock_agent/agent/graph.py"""

from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
# 导入所有 node 函数
from agent.nodes.supervisor_node import supervisor_node
from agent.nodes.profile_node import profile_node
from agent.nodes.fundamental_node import fundamental_node
from agent.nodes.technical_node import technical_node
from agent.nodes.news_node import news_node
from agent.nodes.synthesizer_node import synthesizer_node
from agent.nodes.reflection_node import reflection_node
from agent.nodes.eval_node import eval_node
from shared.agents.agent_state import AgentState
from shared.agents.checkpoint import get_aredis_checkpointer

from event.event_manager import event


def build_investment_agent(checkpointer):
    """生产级 Graph 构建函数"""
    workflow = StateGraph(AgentState)
    
    # 统一 retry 配置
    default_retry = RetryPolicy(max_attempts=3, retry_on=[Exception])  # 可自定义异常
    
    workflow.add_node("supervisor", supervisor_node, retry_policy=default_retry)
    workflow.add_node("profile", profile_node)
    workflow.add_node("fundamental", fundamental_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("news", news_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("eval", eval_node)
    
    # 边（并行结构清晰）
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "profile")
    
    workflow.add_edge("profile", "fundamental")
    workflow.add_edge("profile", "technical")
    workflow.add_edge("profile", "news")
    
    workflow.add_edge("fundamental", "synthesizer")
    workflow.add_edge("technical", "synthesizer")
    workflow.add_edge("news", "synthesizer")

    workflow.add_edge("synthesizer", "reflection")
    workflow.add_edge("eval", END)

    def should_continue(state: AgentState) -> str:

        """Reflection 后的决策逻辑"""
        last_reflection = state.get("reflections", [""])[-1].upper()
        retry_count = state.get("retry_count", 0)
        
        if retry_count >= 3 or "PASS" in last_reflection:
            return "eval"  
        
        return "synthesizer"

    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "synthesizer": "synthesizer",
            "eval": "eval" 
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


if __name__ == "__main__":
    from uuid import UUID
    import asyncio
    job_id = uuid4()
    result = asyncio.run(ask_investment("下半年AI应用领域值得投资的股票有哪些？", job_id, "debug"))
    
    print(result.get("final_answer"))
    print(result["messages"][-1].content)

    from shared.db.redis import pop_queue
    while True:
        event = pop_queue("debug")
        if not event:
            break
        print(event)




