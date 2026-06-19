"""agent/tools.py — Stock Agent 工具集"""
import datetime
import os
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from loguru import logger
import pandas as pd
from core.db import get_schema, get_tables, execute_query, engine
from core.minio_file import load_skill as _load_skill, list_skills as _list_skills
from service import search_similar
# from shared.models.ollama import get_llm, get_llm_sql
from shared.models.deepseek import get_deepseek
from data.text_helper import build_stock_profile_text, build_stock_news_text


def _clean_sql(raw: str) -> str:
    return raw.strip().strip("```sql").strip("```").strip()


@tool
def execute_sql(sql: str) -> str:
    """执行任意 SELECT SQL，适合探索数据、验证日期范围、统计分析等。"""
    try:
        rows = execute_query(sql)
        return "无结果" if not rows else str(rows[:50])
    except Exception as e:
        return f"执行失败: {e}"


@tool
def get_db_schema(dummy: str = "") -> str:
    """获取数据库所有表结构，第一步必须调用此工具。"""
    return "\n".join(get_schema())


@tool
def query_database(question: str) -> str:
    """
    将自然语言问题转换为 SQL 并查询 MySQL，自动重试纠错（最多3次）。
    直接输入用户的自然语言问题即可。
    """
    schemas = get_schema()
    tables = get_tables()
    samples = {t: execute_query(f"SELECT * FROM `{t}` LIMIT 1")
               for t in tables}

    context = (
        f"数据库结构：\n" + "\n".join(schemas) + "\n\n"
        f"样本数据：\n" + "\n".join(f"{t}: {s}" for t, s in samples.items())
    )

    sql_agent_prompt = (
        "你是 MySQL 专家。根据数据库结构和样本数据生成 SELECT 语句。\n"
        "只返回纯 SQL，不要 markdown，不要解释。\n"
        "规则：GROUP BY 时 SELECT 里所有非聚合列必须出现在 GROUP BY 中。\n\n"
        + context
    )

    fix_prompt_tpl = (
        "以下 MySQL SQL 执行失败：\n```sql\n{sql}\n```\n"
        "错误信息：{error}\n\n"
        + context + "\n\n只返回修复后的 SQL，不要解释。"
    )

    sql_agent = get_deepseek()
    # 生成初始 SQL
    resp = sql_agent.invoke([
        SystemMessage(content=sql_agent_prompt),
        HumanMessage(content=question),
    ])
    sql = _clean_sql(resp.content)
    logger.debug("Generated SQL: {}", sql)

    # 自动纠错循环
    for attempt in range(3):
        try:
            rows = execute_query(sql)
            if not rows:
                return "查询无结果"
            headers = list(rows[0].keys())
            lines = [" | ".join(headers)]
            lines += [" | ".join(str(r[h]) for h in headers) for r in rows]
            return f"共 {len(rows)} 条：\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("Attempt {} failed: {}", attempt + 1, e)
            if attempt < 2:
                fix_resp = sql_agent.invoke([
                    SystemMessage(
                        content=fix_prompt_tpl.format(sql=sql, error=e))
                ])
                sql = _clean_sql(fix_resp.content)
                logger.debug("Fixed SQL: {}", sql)

    return f"查询失败，最终 SQL：{sql}"


@tool
def time_tool(dummy: str = "") -> str:
    """获取当前时间（精确到秒）"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def load_skill(skill_name: str) -> str:
    """从 MinIO 加载专业技能说明文档。先用 list_skills 查看可用清单。"""
    return _load_skill(skill_name)


@tool
def list_skills(dummy: str = "") -> str:
    """列出 MinIO 中所有可用的 skill 名称"""
    skills = _list_skills()
    return "可用 skills：\n" + "\n".join(f"- {s}" for s in skills)


@tool
def search_business_breakdown(stock_names: str):
    """
    输入：
        stock_names: 所涉及的股票们的名称，用空格隔开
    输出：
        字典类型包含某个企业在这个细分领域，在某个时间的经营情况
    """
    return search_similar.search("stock_business_breakdown", "stock_business_breakdown", stock_names, 5)


@tool
def search_stock_profile(query: str):
    """根据用户的提问中提取出领域，作为query查找相对应的股票
    """
    return search_similar.search_v3(query,
                                    "stock_profile_hybrid",
                                    "stock_profile",
                                    build_stock_profile_text,
                                    20).drop(columns=["scope"]).to_dict(orient="records")


@tool
def search_news(stock_names: str):
    """
    输入：
        stock_names: 所涉及的股票们的名称，用空格隔开
    输出：
        返回关于这个题材或领域里相关的新闻或者所设计的企业的公告
    """
    return search_similar.search_v3(stock_names, 
                                    "stock_news_hybrid", 
                                    "stock_news", 
                                    build_stock_news_text, 20).to_dict(orient="records")


# @tool
def stock_financial_features(codes: list[str]):
    """
    获取指定股票的财务分析数据，包括营收、净利润、ROE、毛利率等关键指标。

    Args:
        codes (list[str]): 股票代码，必须带市场前缀（如 sh601012、sz002837）

    Returns:
        dict: 包含财务指标的字典
    """

    sql = f"SELECT * FROM mydb.financial_feature code in ({str(codes)[1:-1]});"
    df = pd.read_sql(sql, con=engine.connect())
    return df.to_dict(orient="records")


@tool
def stock_financial_analysis(code: str):
    """
    输入的code 格式为 sh601083
    """

    sql = """SELECT * FROM mydb.financial_factor
    where total_financial_rank is not null and code = 
    order by total_financial_rank asc limit 1000;"""
    df = pd.read_sql(sql, con=engine.connect())
    return df.to_dict(orient="records")

@tool
def stock_technical_analysis(query: str):
    """
    get top 1000 stock by technical indicators. caclulated by
     g["ma20_ratio"] = (
            g["close"] /
            g["close"].rolling(20).mean()
        )

        g["ma60_ratio"] = (
            g["close"] /
            g["close"].rolling(60).mean()
        )

        g["ma120_ratio"] = (
            g["close"] /
            g["close"].rolling(120).mean()
        )

        # ---------------------------
        # momentum
        # ---------------------------

        g["rsi14"] = rsi(g["close"], 14)

        g["mom20"] = momentum(g["close"], 20)

        g["macd_hist"] = macd(g["close"])

        # ---------------------------
        # volume
        # ---------------------------

        g["obv"] = obv(
            g["close"],
            g["volume"]
        )

        g["mfi14"] = mfi(
            g["high"],
            g["low"],
            g["close"],
            g["volume"],
            14
        )

    """

    sql = """SELECT * FROM mydb.technical_factor
where date is not null and date > '2025-01-01' and total_technical_score is not null
 order by total_technical_score desc limit 1000;"""
    df = pd.read_sql(sql, con=engine.connect())
    return df.to_dict(orient="records")


web_search = TavilySearch(
    max_results=5, search_depth="advanced", include_answer=True)

DB_TOOLS = [get_db_schema, execute_sql, query_database]
SEARCH_TOOLS = [web_search]
SKILL_TOOLS = [load_skill, list_skills, time_tool]
similar_stock_info_tools = [search_business_breakdown, search_stock_profile,
                            search_news, stock_financial_analysis, stock_technical_analysis]
ALL_TOOLS = DB_TOOLS + SEARCH_TOOLS + SKILL_TOOLS + similar_stock_info_tools


if __name__ == "__main__":
    out = stock_financial_features(["sh601012","sz002837"])
    print(out)