"""src/stock_agent/agent/graph.py"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from agent.error_handler import error_handler_middleware
# 导入所有 node 函数
from agent.nodes.supervisor_node import supervisor_node
from agent.nodes.profile_node import profile_node
from agent.nodes.fundamental_node import fundamental_node
from agent.nodes.technical_node import technical_node
from agent.nodes.news_node import news_node
from agent.nodes.synthesizer_node import synthesizer_node
from agent.nodes.reflection_node import reflection_node
from shared.agents.agent_state import AgentState
from shared.agents.checkpoint import get_redis_checkpointer

from event.event_manager import event


def build_investment_agent(checkpointer=None, thread_id="default"):
    """生产级 Graph 构建函数"""
    workflow = StateGraph(AgentState)
    
    # 统一 retry 配置
    default_retry = RetryPolicy(max_attempts=3, retry_on=[Exception])  # 可自定义异常
    
    workflow.add_node("supervisor", error_handler_middleware(supervisor_node), retry_policy=default_retry)
    workflow.add_node("profile", error_handler_middleware(profile_node))
    workflow.add_node("fundamental", error_handler_middleware(fundamental_node))
    workflow.add_node("technical", error_handler_middleware(technical_node))
    workflow.add_node("news", error_handler_middleware(news_node), retry_policy=RetryPolicy(max_attempts=5))  # news 重试更多
    workflow.add_node("synthesizer", error_handler_middleware(synthesizer_node))
    workflow.add_node("reflection", error_handler_middleware(reflection_node))
    
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

    def should_continue(state: AgentState) -> str:

        """Reflection 后的决策逻辑"""
        last_reflection = state.get("reflections", [""])[-1].upper()
        retry_count = state.get("retry_count", 0)
        
        if retry_count >= 3 or "PASS" in last_reflection:
            event.graph_finish(thread_id, "END", state.get("final_answer", "获取最终答案失败，请查询日志"))
            return END   # 直接结束，不再回 synthesizer
        
        return "synthesizer"

    workflow.add_conditional_edges(
        "reflection",
        should_continue,
        {
            "synthesizer": "synthesizer",
            END: END
        }
    )

    return workflow.compile(
        checkpointer=checkpointer
    )


def ask_investment(question: str, job_id: str, thread_id: str = "default"):
    """推荐入口"""
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50,          # 防止无限循环
    }
    
    with get_redis_checkpointer() as cp:
        cp.setup()
        agent = build_investment_agent(checkpointer=cp, thread_id=thread_id)
        result = agent.invoke({"user_question": question, "thread_id": thread_id, "job_id": job_id}, config=config)
    
    return result



if __name__ == "__main__":
    result = ask_investment("兆易创新已经让我总资产跌了快30%我现在是重仓，接下来该怎么办？", "debug")
    
    print(result.get("final_answer"))
    print(result["messages"][-1].content)
    from shared.db.redis import pop_queue
    while True:
        event = pop_queue("debug")
        if not event:
            break
        print(event)
    # from langsmith import evaluate, Client
    # client = Client()
    # def target(inputs: dict):
    #     """Agent 执行函数 - 必须返回 output"""
    #     question = inputs["user_question"]
    #     answer = ask_investment(question)





    #     return {
    #         "output": answer,                    # 关键字段
    #         "final_answer": answer               # 可选
    #     }

    # # 运行评估
    # evaluate(
    #     target,
    #     data="stock_eval_dataset",
    #     evaluators=["correctness"],              # 先用内置
    #     experiment_prefix="stock_agent_test",
    #     max_concurrency=2
    # )