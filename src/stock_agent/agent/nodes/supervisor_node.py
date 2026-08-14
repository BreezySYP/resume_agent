
from typing import Any, Dict

from agent.tools import time_tool
from event.decorator import node
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from shared.agents.agent_state import CLEAR_MARK, AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek


class AnalysisPlan(BaseModel):
    current_time: str = Field(...)
    plan_summary: str = Field(...)
    focus_areas: list[str] = Field(...)  # ["fundamental", "technical", "news"]

MAX_MEMORY = 5
@node(node_name="supervisor", title="监督节点")
def supervisor_node(state: AgentState) -> Dict[str, Any]:
    if state["messages"] and len(state["messages"]) >MAX_MEMORY:
        state["messages"] = state["messages"][-MAX_MEMORY:]
    currtime = time_tool.invoke("")

    memory_ctx = state.get("memory_context") or "（暂无相关长期记忆）"
    question = state["user_question"]
    
    system_prompt = SystemMessage(content=f"""
        你是一个专业的A股投资分析主管。
        当前时间：{currtime}

        规则：
        1. 分析用户问题，输出结构化 JSON 分析计划。
        2. 明确 fundamental/technical/news 的优先级。

        ## 用户问题: {question}

        ## 用户长期/中期记忆: {memory_ctx}

        请严格按照以下 JSON 格式输出：
        {AnalysisPlan.model_json_schema()}
    """)

    model_name = "deepseek-chat"
    model = get_deepseek(model=model_name, temperature=0.1)
    parser = JsonOutputParser(pydantic_object=AnalysisPlan)
    chain = model | parser

    try:
        plan = invoke_with_metrics(
            chain, 
            [system_prompt, HumanMessage(content=state["user_question"])], 
            "supervisor",
            model_name=model_name)
        plan['current_time'] = currtime
    except Exception:
        plan = {"current_time": currtime, "plan_summary": "解析失败", "focus_areas": ["fundamental", "news"]}

    return {
        "messages": [state["user_question"]],
        "plan": plan,
        "user_question": state["user_question"],
        "current_time": currtime,
        "errors": [CLEAR_MARK],
        "rag_contexts": [CLEAR_MARK],
        "reflections": []
    }