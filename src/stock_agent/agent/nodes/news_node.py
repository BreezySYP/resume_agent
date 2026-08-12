from typing import Any, Dict
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from shared.agents.agent_state import AgentState
from shared.models.deepseek import get_deepseek
from agent.tools import search_news, tav_search, time_tool
from event.decorator import node
from shared.metrics.prome import invoke_with_metrics

@node(node_name="news", title="新闻数据节点")
def news_node(state: AgentState) -> Dict[str, Any]:
    if not state.get("stock_profile"):
        return {"news_analysis": "No stock profile available."}
    
    current_time = state.get("current_time", time_tool.invoke(""))
    stock_names = " ".join([p.get("name", str(p)) for p in state.get("stock_profile", [])])

    model_name = "deepseek-chat"
    model = get_deepseek(model=model_name, temperature=0.2)
    
    prompt = SystemMessage(content=f"""
        你是新闻分析师。
        当前日期：{current_time}

        针对以下股票：
        {stock_names}

        概念：
        {state['stock_profile']}分析**最新**新闻对股价的影响

        重点维度：情绪、政策利好、机构、风险、热点。
        如果搜索结果差，主动拆分关键词重试。
        """)
            
    # 使用 create_react_agent 获得更好重试能力
    from langchain.agents import create_agent
    agent = create_agent(
        model=model,
        # tools=[search_news, tav_search],
        tools=[search_news],
        system_prompt=prompt
    )
    
    result = invoke_with_metrics(
        agent, 
        {"messages": [HumanMessage(content=state["user_question"])]}, 
        "news", 
        model_name)
    
    tool_outputs = []
    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            tool_outputs.append(msg.content)
        elif isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                tool_outputs.append(f"Tool {call['name']} called with {call['args']}")

    return {
        "news_analysis": result["messages"][-1].content,
        "rag_contexts": tool_outputs,
    }