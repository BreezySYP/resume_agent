import operator
from typing import Annotated, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, HumanMessage

CLEAR_MARK = "__CLEAR__"

def clear_list(left: List, right: List) -> List:
    if right and right[0] == CLEAR_MARK:
        return right[1:]          # 丢掉标记，只保留后面的内容
    return (left or []) + (right or [])

class AgentState(TypedDict):
    messages:       Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    next:           str
    reflections:    List[str]
    final_answer:   str
    human_feedback: str
    ragas_result:   Optional[dict] # 最新一次 RAGAS 评估结果
    user_question:  str
    retry_count:     int
    review_feedback: Optional[str]
    stock_codes: List[str]
    analysis_summary: str
    stock_profile: dict
    stock_technique_factor: dict
    stock_financial_factor: dict
    plan: str
    current_time: str
    errors:  Annotated[List[str], clear_list] = []
    confidence: float = 0.0
    news_analysis: str
    markdown: str
    thread_id: str
    job_id: str
    ragas_result: dict
    memory_context: str
