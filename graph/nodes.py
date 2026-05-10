"""
graph/nodes.py
Supervisor / Researcher / Coder / Reviewer / Reflection / Final_Answer 节点。
Agent 实例在首次调用时懒加载，避免 import 时就初始化模型。
"""
from functools import lru_cache

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config.tracing import tracer
from agents.base import llm, build_researcher, build_coder, build_reviewer
from graph.state import AgentState

# ── 懒加载 Agent（避免模块导入时就连接 Ollama）──────────────────────────────

@lru_cache(maxsize=1)
def _researcher():
    agent = build_researcher()
    print("✅ Researcher Agent 已创建")
    return agent

@lru_cache(maxsize=1)
def _coder():
    agent = build_coder()
    print("✅ Coder Agent 已创建")
    return agent

@lru_cache(maxsize=1)
def _reviewer():
    agent = build_reviewer()
    print("✅ Reviewer Agent 已创建")
    return agent


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


def supervisor_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("supervisor_node"):
        prompt   = _SUPERVISOR_TMPL.format(messages=state["messages"][-8:])
        response = llm.invoke([SystemMessage(content=prompt)])
        decision = response.content.strip().split("\n")[0].strip()
        next_node = _NODE_MAP.get(decision.lower(), decision)
        print(f"🔀 Supervisor → {next_node}")
        return {"next": next_node}


# ── Researcher ────────────────────────────────────────────────────────────────

def researcher_node(state: AgentState) -> dict:
    with tracer.start_as_current_span("researcher_node"):
        print(f"🔍 Researcher ← {state['messages'][-1].content[:60]}...")
        result = _researcher().invoke(state)
        return {"messages": result["messages"]}


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


# ── Final Answer ──────────────────────────────────────────────────────────────

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
        return {"final_answer": text, "messages": state["messages"]}
