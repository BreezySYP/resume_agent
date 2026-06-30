import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from agent.tools import time_tool
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek


class AnalysisPlan(BaseModel):
    current_time: str = Field(...)
    plan_summary: str = Field(...)
    focus_areas: list[Literal["fundamental", "technical", "news"]] = Field(...)

# ====================== Nodes ======================
def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """智能 Supervisor / Planner（最佳实践：输出结构化计划）"""

    system_prompt = SystemMessage(content=f"""
        你是一个专业的A股投资分析主管。
        规则：
        1. 必须先调用 time_tool 获取当前准确日期。
        2. 分析用户问题，输出结构化 JSON 分析计划。
        3. 计划中明确各维度（fundamental/technical/news）的优先级。

        请严格按照以下JSON格式输出：
        { AnalysisPlan.model_json_schema() }
        """)

    model = get_deepseek() | JsonOutputParser(pydantic_object=AnalysisPlan)
    messages = [system_prompt, HumanMessage(content=state["user_question"])]
    currtime = time_tool.invoke("")
    plan = model.invoke(messages)
    plan['current_time'] = currtime

    return {
            "messages": messages + [SystemMessage(content=f"Plan: {str(plan)}")],
            "plan": str(plan),           # 存成 dict，方便下游使用
            "user_question": state["user_question"],
            "current_time": currtime
        }