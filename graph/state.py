"""
graph/state.py
LangGraph 状态定义。
"""
from typing import TypedDict, Annotated, List, Sequence
import operator
from langchain_core.messages import HumanMessage, AIMessage


class AgentState(TypedDict):
    messages:       Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    next:           str
    reflections:    List[str]
    final_answer:   str
    human_feedback: str
