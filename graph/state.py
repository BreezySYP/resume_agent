"""
graph/state.py
LangGraph 状态定义。
"""
from typing import TypedDict, Annotated, List, Sequence, Optional
import operator
from langchain_core.messages import HumanMessage, AIMessage


class AgentState(TypedDict):
    messages:       Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    next:           str
    reflections:    List[str]
    final_answer:   str
    human_feedback: str
    rag_contexts:   List[str]        # Researcher 收集的检索内容，供 RAGAS 使用
    ragas_result:   Optional[dict]   # 最新一次 RAGAS 评估结果
