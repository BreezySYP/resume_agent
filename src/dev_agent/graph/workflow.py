"""graph/workflow.py — StateGraph 组装"""
from langgraph.graph import StateGraph, START, END
from shared.agents.agent_state import AgentState
from graph.nodes import (
    capitalist_node, entry_node, generalist_node,  reflection_node, final_answer_node, supervisor_node,
)


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    # g.add_node("Entry",       entry_node)
    g.add_node("Supervisor",  supervisor_node)     
    g.add_node("Capitalist",  capitalist_node)
    g.add_node("Generalist",  generalist_node)
    g.add_node("Reflection",  reflection_node)
    g.add_node("Final_Answer", final_answer_node)

    # g.add_edge(START, "Entry")
    # g.add_edge("Entry", "Supervisor")
    g.add_edge(START, "Supervisor")

    g.add_conditional_edges(
        "Supervisor",
        lambda s: s.get("next", "Final_Answer"),
        {
            "Capitalist": "Capitalist", 
            "Generalist": "Generalist", 
            "Final_Answer": "Final_Answer"
         },
    )

    g.add_edge("Generalist",  "Reflection")
    g.add_edge("Capitalist",  "Reflection")
    g.add_edge("Reflection",  "Supervisor")
    # g.add_edge("Reflection",  "Final_Answer")
    g.add_edge("Final_Answer", END)
    return g
