"""
graph/nodes.py
Supervisor / Researcher / Coder / Reviewer / Reflection / Final_Answer 节点。
Final_Answer 完成后自动触发 RAGAS 评估。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from  configs.tracing import tracer
from  agents.base import llm, build_researcher, build_coder, build_reviewer
from  graph.state import AgentState

# ── 懒加载 Agent ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _researcher():
    a = build_researcher(); print("✅ Researcher ready"); return a

@lru_cache(maxsize=1)
def _coder():
    a = build_coder(); print("✅ Coder ready"); return a

@lru_cache(maxsize=1)
def _reviewer():
    a = build_reviewer(); print("✅ Reviewer ready"); return a


# ── Supervisor ────────────────────────────────────────────────────────────────

_SUPERVISOR_TMPL = """你是一个严格且高效的 Supervisor。

可用节点：
- Researcher：需要搜索信息或最新最佳实践时使用
- Coder：需要编写代码时使用
- Reviewer：需要审查代码时使用
- Final_Answer：任务已完成时使用

路由规则：
- 刚完成 Coding → Reviewer
- 刚完成 Review → Final_Answer
- 不要在 Reviewer 和 Reflection 之间反复循环

只返回节点名称（Researcher / Coder / Reviewer / Final_Answer），不要解释。

当前对话历史：{messages}"""

_NODE_MAP = {
    "final_answer": "Final_Answer",
    "final":        "Final_Answer",
    "结束":          "Final_Answer",
    "完成":          "Final_Answer",
}


_INFO_CHECK_TMPL = """判断当前对话中用户提供的信息是否足够继续执行任务。

对话历史：{messages}

只输出 JSON，不要有其他内容：
{{"enough": true/false, "question": "如果不够填写需要问用户的问题，够的话填null"}}"""
MAX_HISTORY=10

def supervisor_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("supervisor_node"):
        messages = state["messages"][-MAX_HISTORY:]
        # import json

        # # ── 前置：信息充分性检查 ──────────────────────────────
        # check_prompt = _INFO_CHECK_TMPL.format(messages=messages)
        # raw = llm.invoke([SystemMessage(content=check_prompt)]).content.strip()
        # try:
        #     check = json.loads(raw)
        # except Exception:
        #     check = {"enough": True}

        # if not check.get("enough", False):
        #     return {"next": "Final_Answer"}

        ## old
        prompt    = _SUPERVISOR_TMPL.format(messages=messages)
        response  = llm.invoke([SystemMessage(content=prompt)])
        decision  = response.content.strip().split("\n")[0].strip()
        next_node = _NODE_MAP.get(decision.lower(), decision)
        print(f"🔀 Supervisor → {next_node}")
        return {"next": next_node}


# ── Researcher ────────────────────────────────────────────────────────────────

def researcher_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("researcher_node"):
        print(f"🔍 Researcher ← {state['messages'][-1].content[:60]}...")
        result = _researcher().invoke(state)

        # 收集 tool 返回内容供 RAGAS 使用
        tool_contents = [
            m.content for m in result["messages"]
            if hasattr(m, "type") and getattr(m, "type", "") == "tool"
        ]
        update: dict[str, Any] = {"messages": result["messages"]}
        if tool_contents:
            existing = state.get("rag_contexts") or []
            update["rag_contexts"] = existing + tool_contents
        return update


# ── Coder ─────────────────────────────────────────────────────────────────────

def coder_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("coder_node"):
        print(f"💻 Coder ← {state['messages'][-1].content[:60]}...")
        result = _coder().invoke(state)
        return {"messages": result["messages"]}


# ── Reviewer ──────────────────────────────────────────────────────────────────

def reviewer_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("reviewer_node"):
        print(f"🔎 Reviewer ← {state['messages'][-1].content[:60]}...")
        result = _reviewer().invoke(state)
        return {"messages": result["messages"]}


# ── Reflection ────────────────────────────────────────────────────────────────

_REFLECTION_TMPL = """你是一个专业的反思节点。
对当前工作进行总结，明确判断下一步应该怎么做。

当前历史：{messages}

输出格式：
总结：...
问题：...
下一步建议：（Reviewer / Coder / Final_Answer 中选一个）"""


def reflection_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("reflection_node"):
        prompt   = _REFLECTION_TMPL.format(messages=state["messages"][-10:])
        response = llm.invoke([SystemMessage(content=prompt)])
        text     = response.content
        print(f"🤔 Reflection: {text[:120]}...")
        return {
            "reflections": [text],
            "messages":    [HumanMessage(content=f"[Reflection] {text}")],
        }


# ── Final Answer（含 RAGAS 自动评估）─────────────────────────────────────────

def final_answer_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("final_answer_node"):
       
        last_ai = next(
            (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
            None,
        )
        text = last_ai.content if last_ai else state["messages"][-1].content

        if state.get("reflections"):
            text += "\n\n【系统反思】\n" + "\n".join(state["reflections"])
        if state.get("human_feedback"):
            text += f"\n\n【用户反馈】：{state['human_feedback']}"

        print(f"✅ Final Answer: {text[:80]}...")

        ragas_result = _run_ragas_async(state, text)

        return {
            "final_answer": text,
            "messages":     state["messages"],
            "ragas_result": ragas_result,
        }


def _run_ragas_async(state: AgentState, answer: str) -> dict | None:
    """后台线程跑 RAGAS，不阻塞 Final Answer 返回。"""
    import threading

    first_human = next(
        (m for m in state["messages"]
         if isinstance(m, HumanMessage) and not m.content.startswith("[Reflection]")),
        None,
    )
    if not first_human:
        return None

    question = first_human.content
    contexts = state.get("rag_contexts") or []
    result_holder: dict[str, Any] = {}

    def _eval():
        try:
            from  ragas_eval.evaluator import run_ragas
            scores = run_ragas(question=question, contexts=contexts,
                               answer=answer, llm=llm)
            result_holder.update(scores)
        except Exception as e:
            print(f"⚠️  RAGAS 线程异常: {e}")

    t = threading.Thread(target=_eval, daemon=True)
    t.start()
    t.join(timeout=120)
    return result_holder or None
