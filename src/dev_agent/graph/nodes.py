"""graph/nodes.py — 所有 LangGraph 节点"""
from __future__ import annotations
from functools import lru_cache
import os
from typing import Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from loguru import logger
from shared.configs.settings import GRAPH_CONFIG
from shared.configs.tracing import tracer
from shared.models.ollama_models import get_llm
from agents.base import build_generalist
from shared.agents.agent_state import AgentState

MAX_HISTORY = 10

# @lru_cache(maxsize=1)
# def _researcher(): return build_researcher()

# @lru_cache(maxsize=1)
# def _coder(): return build_coder()

# @lru_cache(maxsize=1)
# def _reviewer(): return build_reviewer()

@lru_cache(maxsize=1)
def _generalist(): return build_generalist()

def entry_node(state: AgentState) -> dict:
    """入口节点：提取并保存用户原始问题"""
    user_question = ""
    if state.get("messages"):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            user_question = last.content.strip()
    logger.info(f"🔍 Entry: {user_question[:80]}")
    return {"user_question": user_question}


_SUPERVISOR_TMPL = """你是一个严格且高效的 Supervisor。

可用节点：
Capitalist： 尚未解答用户的投资相关的问题
Generalist： 尚未解答用户的非投资相关的问题
Final_Answer： 已经解答了用户问题并整理好答案返回给用户，或者缺乏高达80%以上的信息才能回答用户问题

路由规则：
- 根据用户问题，以及历史对话记录，按照节点规则返回3个节点 Capitalis/Generalist/Final_Answer 中的一个
- 不要反复循环

当前历史：{messages}
用户问题：{user_question}

只返回节点名称，不要解释。"""

_NODE_MAP = {
    "final_answer": "Final_Answer",
    "final":        "Final_Answer",
    "结束":          "Final_Answer",
    "完成":          "Final_Answer",
}


def supervisor_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("supervisor_node"):
        prompt   = _SUPERVISOR_TMPL.format(
            messages=state["messages"][-MAX_HISTORY:],
            user_question=state["user_question"],
        )
        response  = get_llm().invoke([SystemMessage(content=prompt)])
        decision  = response.content.strip().split("\n")[0].strip()
        next_node = _NODE_MAP.get(decision.lower(), decision)
        logger.info(f"🔀 Supervisor → {next_node}")
        return {"next": next_node}


# def researcher_node(state: AgentState) -> dict:
#     with tracer.start_as_current_span("researcher_node"):
#         result        = _researcher().invoke(state)
#         tool_contents = [m.content for m in result["messages"] if getattr(m, "type", "") == "tool"]
#         update: dict[str, Any] = {"messages": result["messages"]}
#         if tool_contents:
#             update["rag_contexts"] = (state.get("rag_contexts") or []) + tool_contents
#         return update


# def coder_node(state: AgentState) -> dict:
#     with tracer.start_as_current_span("coder_node"):
#         result = _coder().invoke(state)
#         return {"messages": result["messages"]}


# def reviewer_node(state: AgentState) -> dict:
#     with tracer.start_as_current_span("reviewer_node"):
#         result = _reviewer().invoke(state)
#         return {"messages": result["messages"]}


from langgraph.pregel.remote import RemoteGraph
_stock_remote = RemoteGraph(
    "stock_agent",
    url=os.getenv("STOCK_AGENT_URL", "http://localhost:8002"),
)

def capitalist_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("capitalist_node"):
        result = _stock_remote.invoke(
            {
                "messages":        state["messages"],
                "user_question":   state["user_question"],
                "retry_count":     0,
                "review_feedback": None,
            },
            config=GRAPH_CONFIG,
        )
        return {"messages": result["messages"]}

def generalist_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("generalist_node"):
        result = _generalist().invoke(state)
        return {"messages": result["messages"]}


_REFLECTION_TMPL = """你是专业的反思节点。对当前工作总结，判断下一步。

历史：{messages}

输出格式：
总结：...
问题：...
根据用户问题 {user_question}，下一步建议：（Generalist / Final_Answer）"""


def reflection_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("reflection_node"):
        prompt   = _REFLECTION_TMPL.format(
            messages=state["messages"][-10:],
            user_question=state["user_question"],
        )
        response = get_llm().invoke([SystemMessage(content=prompt)])
        text     = response.content
        logger.info(f"🤔 Reflection: {text[:100]}")
        return {
            "reflections": [text],
            "messages":    [HumanMessage(content=f"[Reflection] {text}")],
        }
    


_FINAL_TMPL = """总结历史对话，回答用户问题。
历史：{messages}
用户问题：{user_question}
直接给出最终答案，不要解释。"""


def final_answer_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("final_answer_node"):
        response = get_llm().invoke([SystemMessage(content=_FINAL_TMPL.format(
            messages=state["messages"],
            user_question=state["user_question"],
        ))])
        text = response.content.strip()
        if state.get("reflections"):
            text += "\n\n【系统反思】\n" + "\n".join(state["reflections"])
        if state.get("human_feedback"):
            text += f"\n\n【用户反馈】：{state['human_feedback']}"
        logger.info(f"✅ Final: {text[:80]}")
        ragas_result = _run_ragas_async(state, text)
        return {"final_answer": text, "messages": state["messages"], "ragas_result": ragas_result}


def _run_ragas_async(state: AgentState, answer: str) -> dict | None:
    import threading
    first_human = next(
        (m for m in state["messages"] if isinstance(m, HumanMessage) and not m.content.startswith("[Reflection]")),
        None,
    )
    if not first_human:
        return None
    result_holder: dict[str, Any] = {}

    def _eval():
        try:
            from packages.ragas_eval.evaluator import run_ragas
            scores = run_ragas(
                question=first_human.content,
                contexts=state.get("rag_contexts") or [],
                answer=answer,
                llm=get_llm(),
            )
            result_holder.update(scores)
        except Exception as e:
            logger.info(f"⚠️  RAGAS 线程异常: {e}")

    t = threading.Thread(target=_eval, daemon=True)
    t.start(); t.join(timeout=120)
    return result_holder or None
