"""agent/tools.py — Stock Agent 工具集"""
import datetime
import os
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from loguru import logger
from core.db import get_schema, get_tables, execute_query
from core.minio_file import load_skill as _load_skill, list_skills as _list_skills
from shared.models.ollama import get_llm, get_llm_sql


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
    """自然语言 → SQL → 执行，含自动纠错（最多3次）。"""
    schemas = get_schema()
    tables  = get_tables()
    samples = {t: execute_query(f"SELECT * FROM `{t}` LIMIT 1") for t in tables}
    context = (
        "数据库结构：\n" + "\n".join(schemas) + "\n\n"
        "样本数据：\n"  + "\n".join(f"{t}: {s}" for t, s in samples.items())
    )
    sql_prompt = (
        "你是 MySQL 专家。根据结构和样本生成 SELECT 语句。\n"
        "只返回纯 SQL，不要 markdown。\n"
        "规则：GROUP BY 时 SELECT 里所有非聚合列必须出现在 GROUP BY 中。\n\n"
        + context
    )
    fix_tpl = (
        "以下 MySQL SQL 执行失败：\n```sql\n{sql}\n```\n"
        "错误信息：{error}\n\n" + context + "\n\n只返回修复后的 SQL。"
    )
    resp = get_llm_sql().invoke([SystemMessage(content=sql_prompt), HumanMessage(content=question)])
    sql  = _clean_sql(resp.content)
    logger.debug("Generated SQL: {}", sql)

    for attempt in range(3):
        try:
            rows = execute_query(sql)
            if not rows:
                return "查询无结果"
            headers = list(rows[0].keys())
            lines   = [" | ".join(headers)]
            lines  += [" | ".join(str(r[h]) for h in headers) for r in rows]
            return f"共 {len(rows)} 条：\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("Attempt {} failed: {}", attempt + 1, e)
            if attempt < 2:
                fix_resp = get_llm_sql().invoke([SystemMessage(content=fix_tpl.format(sql=sql, error=e))])
                sql      = _clean_sql(fix_resp.content)
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

web_search = TavilySearch(max_results=5, search_depth="advanced", include_answer=True)

DB_TOOLS     = [get_db_schema, execute_sql, query_database]
SEARCH_TOOLS = [web_search]
SKILL_TOOLS  = [load_skill, list_skills, time_tool]
ALL_TOOLS    = DB_TOOLS + SEARCH_TOOLS + SKILL_TOOLS
