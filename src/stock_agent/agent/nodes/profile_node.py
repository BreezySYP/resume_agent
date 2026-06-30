import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from agent.tools import search_stock_profile
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek

def profile_node(state: AgentState) -> Dict[str, Any]:
    """股票画像节点"""
    model = get_deepseek()
    prompt = HumanMessage(content=f"""
        根据以下用户问题提取关键股票/公司关键词：
        {state["user_question"]}
        只返回关键词列表或公司名称，简洁无解释。
        """)
    
    keywords = model.invoke([prompt])
    
    try:
        profile = search_stock_profile.invoke(keywords.content)
        return {
            "stock_profile": profile or [],
            "messages": state.get("messages", []) + [
                SystemMessage(content=f"已获取 {len(profile) if isinstance(profile, list) else 0} 个股票画像")
            ]
        }
    except Exception as e:
        return {"stock_profile": [], "error": str(e)}