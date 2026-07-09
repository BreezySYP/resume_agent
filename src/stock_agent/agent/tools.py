"""agent/tools.py — Stock Agent 工具集"""
import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from core.minio_file import list_skills as _list_skills
from core.minio_file import load_skill as _load_skill
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from loguru import logger
from service import search_similar
from shared.db.mysql import engine, execute_query, get_schema, get_tables
from shared.models.deepseek import get_deepseek
from shared.text.stock_text import build_stock_news_text, build_stock_profile_text


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
    samples = {t: execute_query(f"SELECT * FROM `{t}` LIMIT 1") for t in tables}

    context = (
        "数据库结构：\n" + "\n".join(schemas) + "\n\n"
        "样本数据：\n" + "\n".join(f"{t}: {s}" for t, s in samples.items())
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
    resp = sql_agent.invoke([SystemMessage(content=sql_agent_prompt), HumanMessage(content=question)])
    sql = _clean_sql(resp.content)
    logger.debug("Generated SQL: {}", sql)

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
                fix_resp = sql_agent.invoke([SystemMessage(content=fix_prompt_tpl.format(sql=sql, error=e))])
                sql = _clean_sql(fix_resp.content)
                logger.debug("Fixed SQL: {}", sql)

    return f"查询失败，最终 SQL：{sql}"


@tool
def time_tool() -> str:
    """获取当前时间（精确到秒）"""
    return datetime.datetime.now(ZoneInfo('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")


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
    """根据用户的提问中提取出领域，作为query查找相对应的股票"""
    return search_similar.search_with_rerank(
        query, "stock_profile_hybrid", "stock_profile", build_stock_profile_text, 20
    )


@tool
def search_news(stock_names: str):
    """
    输入：
        stock_names: 所涉及的股票们的名称，用空格隔开
    输出：
        返回关于这个题材或领域里相关的新闻或者所设计的企业的公告
    """
    return search_similar.search_with_rerank(
        stock_names, "stock_news_hybrid", "stock_news", build_stock_news_text, 20
    ).to_dict(orient="records")


@tool
def stock_financial_analysis(code: str):
    """输入的code 格式为 sh601083"""
    sql = """SELECT * FROM financial_factor
    WHERE total_financial_rank IS NOT NULL
    ORDER BY total_financial_rank ASC LIMIT 1000;"""
    df = pd.read_sql(sql, con=engine.connect())
    return df.to_dict(orient="records")


@tool
def stock_technical_analysis(query: str):
    """获取近期技术面综合得分排名前 1000 的股票，得分由趋势/动量/量能因子加权计算（详见 stock_etl.factors.technical）"""
    sql = """SELECT * FROM technical_factor
    WHERE date IS NOT NULL AND date > '2025-01-01' AND total_technical_score IS NOT NULL
    ORDER BY total_technical_score DESC LIMIT 1000;"""
    df = pd.read_sql(sql, con=engine.connect())
    return df.to_dict(orient="records")


tav_search = TavilySearch(max_results=5, search_depth="advanced", include_answer=True)

DB_TOOLS = [get_db_schema, execute_sql, query_database]
SEARCH_TOOLS = [tav_search]
SKILL_TOOLS = [load_skill, list_skills, time_tool]
SIMILAR_STOCK_INFO_TOOLS = [search_business_breakdown, search_stock_profile, search_news, stock_financial_analysis, stock_technical_analysis]
ALL_TOOLS = DB_TOOLS + SEARCH_TOOLS + SKILL_TOOLS + SIMILAR_STOCK_INFO_TOOLS
