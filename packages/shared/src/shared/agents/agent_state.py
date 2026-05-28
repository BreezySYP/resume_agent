import operator
from typing import List, Optional, Sequence, TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

class AgentState(TypedDict):
    messages:       Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    next:           str
    reflections:    List[str]
    final_answer:   str
    human_feedback: str
    rag_contexts:   List[str]      # Researcher 收集的检索内容，供 RAGAS 使用
    ragas_result:   Optional[dict] # 最新一次 RAGAS 评估结果
    user_question:  str
    final_answer:    str
    retry_count:     int
    review_feedback: Optional[str]