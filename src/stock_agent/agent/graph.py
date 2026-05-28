"""agent/graph.py — Stock Agent LangGraph"""
import json
from typing import Annotated, Sequence, TypedDict, Optional
import operator

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from loguru import logger

from shared.models.ollama import get_llm
from agent.tools import ALL_TOOLS
from shared.agents.agent_state import AgentState

MAX_RETRY = 2


AGENT_PROMPT = SystemMessage(content=(
    "你是专业的A股分析师，同时掌握数据库查询和市场资讯搜索能力。\n\n"
    "## 工具使用策略\n"
    "- get_db_schema  : 第一步必须调用，了解本地数据库表结构\n"
    "- execute_sql    : 直接执行 SQL 探索数据（日期范围、样本、统计等）\n"
    "- query_database : 自然语言 → SQL，含自动纠错，适合最终查询\n"
    "- web_search     : 搜索实时新闻、政策、公司公告、行业分析\n"
    "- time_tool      : 获取当前时间，计算日期区间时使用\n"
    "- load_skill     : 加载专业领域指导文档\n\n"
    "## 禁止行为\n"
    "- 禁止在未调用工具的情况下直接回答数据类问题\n"
    "- 禁止停下来向用户提问\n"
    "- 禁止使用高度复杂的相关子查询，改用多步简单 SQL\n\n"
    "## MySQL 规则\n"
    "- GROUP BY 时 SELECT 里所有非聚合列必须出现在 GROUP BY 中\n"
    "## 如果收到 Review 反馈\n"
    "- 仔细阅读反馈中指出的问题，重新执行查询修正错误\n"
))

REVIEW_PROMPT = """你是A股数据分析结果的审核专家。
用户问题：{user_question}
Agent 的回答：{answer}

检查：
1. 涨幅计算是否正确（必须是区间首末收盘价对比，SUM(price_change) 不是涨幅）
2. 数据量级是否合理（月涨幅超500%应质疑）
3. 结果数量是否符合要求
4. 是否有明显逻辑错误

只输出 JSON：
{{"approved": true/false, "reason": "原因", "suggestion": "修正建议"}}"""


def agent_node(state: AgentState) -> dict:
    agent    = create_agent(model=get_llm(), tools=ALL_TOOLS, system_prompt=AGENT_PROMPT)
    feedback = state.get("review_feedback")
    messages = list(state["messages"])
    if feedback:
        messages.append(HumanMessage(content=(
            f"[Review 审核未通过，请在原有基础上修正]\n\n问题：{feedback}\n\n"
            "请直接修正 SQL 重新查询，不需要重新获取表结构。"
        )))
        logger.info("🔄 Agent retry with feedback")
    result = agent.invoke({"messages": messages})
    return {"messages": result["messages"], "review_feedback": None}


def review_node(state: AgentState) -> dict:
    last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)
    if not last_ai:
        return {"review_feedback": "没有找到 AI 回答", "retry_count": state.get("retry_count", 0) + 1}

    prompt   = REVIEW_PROMPT.format(user_question=state["user_question"], answer=last_ai.content)
    response = get_llm().invoke([SystemMessage(content=prompt)])
    logger.info("📋 Review raw: {}", response.content)

    try:
        raw    = response.content.strip().strip("```json").strip("```").strip()
        result = json.loads(raw)
    except Exception:
        logger.warning("Review parse failed, auto approve")
        return {"review_feedback": None, "retry_count": state.get("retry_count", 0)}

    if result.get("approved", True):
        return {"review_feedback": None, "retry_count": state.get("retry_count", 0)}
    else:
        feedback = f"问题：{result.get('reason', '')}\n修正建议：{result.get('suggestion', '')}"
        logger.info("❌ Review rejected: {}", feedback)
        return {"review_feedback": feedback, "retry_count": state.get("retry_count", 0) + 1}


def should_retry(state: AgentState) -> str:
    feedback    = state.get("review_feedback")
    retry_count = state.get("retry_count", 0)
    logger.info("should_retry: feedback={} count={}", feedback, retry_count)
    return "retry" if feedback and retry_count <= MAX_RETRY else "done"


def final_node(state: AgentState) -> dict:
    last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)
    return {"final_answer": last_ai.content if last_ai else "无结果"}


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("Agent",  agent_node)
    g.add_node("Review", review_node)
    g.add_node("Final",  final_node)
    g.add_edge(START, "Agent")
    g.add_edge("Agent", "Review")
    g.add_conditional_edges("Review", should_retry, {"retry": "Agent", "done": "Final"})
    g.add_edge("Final", END)
    return g
