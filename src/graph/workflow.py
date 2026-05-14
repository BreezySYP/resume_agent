"""
graph/workflow.py
StateGraph 组装。compile() 在 main.py 中调用（传入 checkpointer）。
"""
from langgraph.graph import StateGraph, START, END

import streamlit as st
from  graph.state import AgentState
from  graph.nodes import (
    supervisor_node,
    researcher_node,
    coder_node,
    reviewer_node,
    reflection_node,
    final_answer_node,
    entry_node
)

@st.cache_resource
def build_graph() -> StateGraph:
    """返回未编译的 StateGraph，由调用方传入 checkpointer 后编译。"""
    g = StateGraph(AgentState)
    g.add_node("Entry", entry_node)
    g.add_node("Supervisor",   supervisor_node)
    g.add_node("Researcher",   researcher_node)
    g.add_node("Coder",        coder_node)
    g.add_node("Reviewer",     reviewer_node)
    g.add_node("Reflection",   reflection_node)
    g.add_node("Final_Answer", final_answer_node)


    g.add_conditional_edges(
        "Supervisor",
        lambda s: s.get("next", "Final_Answer"),
        {
            "Researcher":   "Researcher",
            "Coder":        "Coder",
            "Reviewer":     "Reviewer",
            "Final_Answer": "Final_Answer",
        },
    )

    g.add_edge(START, "Entry")
    g.add_edge("Entry", "Supervisor")
    g.add_edge("Researcher",   "Reflection")
    g.add_edge("Reflection",   "Supervisor")   # 回 Supervisor，不直接结束
    g.add_edge("Coder",        "Supervisor")
    g.add_edge("Reviewer",     "Final_Answer")   # 评审后直接结束，不回 Supervisor
    g.add_edge("Final_Answer", END)

    return g
