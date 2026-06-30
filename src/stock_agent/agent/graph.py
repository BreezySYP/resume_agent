"""src/stock_agent/agent/graph.py
投资分析 Agent - Stage 1 重构（最佳实践版）
目标：可靠、可扩展、可观测、易于长期迭代
"""

import datetime
from typing import Dict, Any, Literal
from zoneinfo import ZoneInfo
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy
from langchain.agents import create_agent
from shared.agents.agent_state import AgentState
from shared.code_rule import add_prefix, remove_prefix
from shared.db.mysql import engine
from shared.models.deepseek import get_deepseek
from langchain_core.output_parsers import JsonOutputParser
from agent.tools import search_news, search_stock_profile, time_tool, tav_search
from pydantic import BaseModel, Field
from agent.nodes import supervisor_node, profile_node, fundamental_node, technical_node, news_node,  synthesizer_node


# ====================== 工具节点 ======================
tools = [time_tool, tav_search, search_news]
tool_node = ToolNode(tools)

# ====================== Graph Builder ======================
def build_investment_agent(
    checkpointer: BaseCheckpointSaver | None = None
):
    """推荐的生产级 Graph 构建函数"""
    workflow = StateGraph(AgentState)
    
    # 节点
    workflow.add_node("supervisor", supervisor_node.supervisor_node)
    workflow.add_node("profile", profile_node.profile_node)
    workflow.add_node("fundamental", fundamental_node.fundamental_node)
    workflow.add_node("technical", technical_node.technical_node)
    workflow.add_node("news", news_node.news_node, retry_policy=RetryPolicy(max_attempts=3))
    workflow.add_node("tools", tool_node)          # 统一工具节点
    workflow.add_node("synthesizer", synthesizer_node.synthesizer_node)
    
    # 边（并行 + 可扩展）
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "profile")
    
    # 并行执行三大分析
    workflow.add_edge("profile", "fundamental")
    workflow.add_edge("profile", "technical")
    workflow.add_edge("profile", "news")
    
    # 汇合
    workflow.add_edge("fundamental", "synthesizer")
    workflow.add_edge("technical", "synthesizer")
    workflow.add_edge("news", "synthesizer")
    
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile(
        checkpointer=checkpointer or MemorySaver()
    )


def ask_investment(question: str, thread_id: str = "default") -> str:
    """推荐调用入口"""
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 30,
    }
    
    agent = build_investment_agent()
    result = agent.invoke({"user_question": question}, config=config)
    return result.get("final_answer", "生成失败")


if __name__ == "__main__":
    print(ask_investment("今年下半年最值得投资的算电协同方面股票是哪几个？"))