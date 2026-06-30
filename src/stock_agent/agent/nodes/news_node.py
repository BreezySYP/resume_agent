import datetime
from typing import Any, Dict, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from agent.tools import search_news, time_tool, tav_search
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek
from langchain.agents import create_agent

tools = [time_tool, tav_search, search_news]

def news_node(state: AgentState) -> Dict[str, Any]:
    """新闻节点 - 使用 ToolNode 风格调用"""
    if not state.get("stock_profile"):
        return {"news_analysis": "No stock profile available."}
    
    prompt = SystemMessage(content=f"""
        你是新闻分析师。针对以下股票分析最新新闻对股价的影响：
        {state['stock_profile']}

        重点维度：股民情绪、政策利好、机构动向、负面风险、热点相关性。
        """)
    
    # model = get_deepseek().bind_tools([search_news, web_search])
    # messages = [prompt] + state.get("messages", [])
    # response = model.invoke(messages)
    
    # response: AIMessage = model.invoke(messages)
    
    # if response.tool_calls:
    #     # 如果模型要调用工具，手动执行并追加 ToolMessage（临时兼容）
    #     tool_results = []
    #     for tool_call in response.tool_calls:
    #         tool = next((t for t in tools if t.name == tool_call["name"]), None)
    #         if tool:
    #             result = tool.invoke(tool_call["args"])
    #             tool_results.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_call["name"]))
        
    #     messages.extend([response] + tool_results)
    #     # 可在此再 invoke 一次让模型总结（可选）
    #     final_response = get_deepseek().invoke(messages)
    #     return {
    #         "news_analysis": final_response.content,
    #         "messages": state.get("messages", []) + [response] + tool_results + [final_response]
    #     }

    agent = create_agent(
        model=get_deepseek(),
        tools = [search_news, tav_search, time_tool],
        system_prompt=prompt
    )
    msg = agent.invoke(state)


    return {
        "news_analysis": msg['messages'][-1].content,
        "messages": state.get("messages", []) + msg["messages"]
    }