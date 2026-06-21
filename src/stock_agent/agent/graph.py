"""agent/graph.py — 投资分析多节点 Agent 工作流"""
import pandas as pd
from agent.prompt import SYNTHESIZER_PROMPT
from agent.tools import search_news, search_stock_profile, time_tool, web_search
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from shared.agents.agent_state import AgentState
from shared.code_rule import add_prefix, remove_prefix
from shared.db.mysql import engine
from shared.models.deepseek import get_deepseek

# ====================== Nodes ======================


def supervisor(state: AgentState):
    """决策节点：先获取当前时间，为后续分析提供时间锚点"""
    agent = create_agent(
        model=get_deepseek(),
        tools=[time_tool, web_search],
        system_prompt=SystemMessage(content="首先通过time_tool工具获取到今天时间，这个最重要。"),
    )
    agent.invoke(state)
    return state


def profile_node(state: AgentState):
    model = get_deepseek()
    prompt = f"""
    根据用户问题： {state["user_question"]} 提取出符合股市投资的关键字，用于向量数据库搜索对应股票信息，直接返回我需要的关键字，能直接发送给数据库，其它什么都不要回答
    """
    key_words = model.invoke(prompt)
    profile = search_stock_profile.invoke(key_words.content)
    return {"stock_profile": profile}


def news_node(state: AgentState):
    prompt = f"""
    你是新闻分析师，重点关注最新事件对股价的潜在影响，追踪近期热点信息，获得热门板块信息等，股民情绪等。

    对于 所涉及到的股票 {state['stock_profile']}

    获取到它们的新闻公告从而给每个股票打分

    打分标准为
    1. 股民对股票的情绪如何
    2. 有没有重大利好政策
    3. 各大银行对于股票的持仓情况
    4. 有没有负面消息等
    5. 是否贴近用户关注的热点
    6. 等等其它因素

    结果显示，用简洁直观的表格展示，但是要包含所有重要信息，存放在上下文中，不是最终展示结果，不必花里胡哨
    """
    agent = create_agent(model=get_deepseek(), tools=[search_news, web_search], system_prompt=SystemMessage(content=prompt))
    result = agent.invoke(state)
    return {"messages": [result["messages"][-1]]}


def fundamental_node(state: AgentState):
    codes = [add_prefix(profile["code"]) for profile in state["stock_profile"]]
    sql = f"""
        SELECT t.* FROM financial_factor t
        JOIN (
            SELECT code, MAX(report_date) AS max_date FROM financial_factor
            WHERE code IN ({str(codes)[1:-1]}) GROUP BY code
        ) latest ON t.code = latest.code AND t.report_date = latest.max_date;
    """
    financial_factor = pd.read_sql(sql, con=engine.connect()).round(2).to_dict(orient="records")
    return {"stock_financial_factor": financial_factor}


def technical_node(state: AgentState):
    codes = [int(remove_prefix(profile["code"])) for profile in state["stock_profile"]]
    sql = f"""
        SELECT t.* FROM technical_factor t
        JOIN (
            SELECT code, MAX(date) AS max_date FROM technical_factor
            WHERE code IN ({str(codes)[1:-1]}) GROUP BY code
        ) latest ON t.code = latest.code AND t.date = latest.max_date;
    """
    technique_factor = pd.read_sql(sql, con=engine.connect()).round(2).to_dict(orient="records")
    return {"stock_technique_factor": technique_factor}


def synthesizer(state: AgentState):
    """最终合成节点"""
    llm = get_deepseek()
    context = "\n\n".join(msg.content for msg in state["messages"] if hasattr(msg, "content"))
    final_prompt = SYNTHESIZER_PROMPT.content.format(
        profile=state["stock_profile"],
        financial=state["stock_financial_factor"],
        technique=state["stock_technique_factor"],
        context=context,
        question=state["user_question"],
    )
    response = llm.invoke([SystemMessage(content=final_prompt)])
    return {"final_answer": response.content, "messages": state["messages"] + [response]}


# ====================== Build Graph ======================
def build_investment_agent(checkpointer: BaseCheckpointSaver | None = None):
    """构建投资分析工作流；不传 checkpointer 时默认使用内存（仅用于本地调试/CLI）"""
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("profile", profile_node)
    workflow.add_node("news", news_node)
    workflow.add_node("fundamental", fundamental_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("synthesizer", synthesizer)

    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "profile")
    workflow.add_edge("profile", "fundamental")
    workflow.add_edge("fundamental", "technical")
    workflow.add_edge("technical", "news")
    workflow.add_edge("news", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


def ask_investment(question: str, thread_id: str = "1") -> str:
    config = {"configurable": {"thread_id": thread_id}}
    agent = build_investment_agent()
    result = agent.invoke({"user_question": question}, config=config)
    return result["final_answer"]


def df_agent(query: str) -> str:
    """备用入口：直接用 SQL Agent 在 stock_profile 表上做自然语言检索"""
    from langchain_community.agent_toolkits import create_sql_agent
    from langchain_community.utilities import SQLDatabase
    from langchain_core.messages import SystemMessage as SysMsg

    db = SQLDatabase(
        engine=engine,
        include_tables=["stock_profile"],
        sample_rows_in_table_info=5,
        custom_table_info={
            "stock_profile": """
                stock_profile 表包含A股上市公司核心信息。
                重要字段：
                - code: 股票代码（如 '002837'）
                - name: 公司名称
                - business: 主营业务（最关键，用于匹配"液冷""数据中心""温控"等）
                - scope: 经营范围（详细描述）
                - update_time: 更新时间
                """
        },
    )
    custom_prefix = """你是一个专业的A股数据分析师。
        目标：根据用户问题从 stock_profile 表中查询相关公司。

        **查询策略**（必须严格遵守）：
        1. 针对 stock_profile， 直接select * from stock_profile，
        2. 根据用户问题提取关键字查找对应行业以及对应股票
        3. **不要** 列出所有表，不要执行 SHOW TABLES

        当前可用表只有：stock_profile
        """
    agent = create_sql_agent(llm=get_deepseek(), db=db, verbose=True, agent_type="tool-calling", handle_parsing_errors=True, max_iterations=15, prefix=custom_prefix)
    response = agent.invoke({"input": query, "messages": [SysMsg(content=custom_prefix)]})
    return response.get("output", str(response))


if __name__ == "__main__":
    print(ask_investment("今年下半年最值得投资的算电协同方面股票是哪几个？"))
