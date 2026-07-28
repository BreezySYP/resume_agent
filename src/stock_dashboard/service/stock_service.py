"""services/stock_service.py — 股票数据查询"""
from __future__ import annotations
import json
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger
from shared.db.redis import redis_cache, redis_client

STOCK_STEPS = ["history", "financial_statement", "profile", "news", "technical"]


def _make_links(code: str, name: str) -> dict:
    # 判断前缀
    prefix = "SH" if code.startswith("6") else "SZ"
    return {
        "eastmoney":    f"https://quote.eastmoney.com/concept/{code}.html",
        "xueqiu":       f"https://xueqiu.com/S/{prefix}{code}",
        "tonghuashun":  f"https://stockpage.10jqka.com.cn/{code}/",
    }


@redis_cache(
    prefix="stock_list",
    key="{page}:{page_size}:{keyword}",
    ttl=1800,
)
def get_stock_list(db: Session, page: int = 1, page_size: int = 50, keyword: str = "") -> dict:
    """
    从 history 表 distinct 获取股票列表，附带最新收盘价和各 step 最新状态。
    """
    offset = (page - 1) * page_size

    # # 基础列表
    # where = "WHERE CAST(code AS CHAR) LIKE :kw OR name LIKE :kw" if keyword else ""
    # kw    = f"%{keyword}%"
    # count_sql = text(f"""
    #     SELECT COUNT(DISTINCT code) FROM history {where}
    # """)
    # list_sql = text(f"""
    #     SELECT
    #         CAST(h.code AS CHAR)  AS code,
    #         MAX(CAST(h.name AS CHAR)) AS name,
    #         MAX(h.close) OVER (PARTITION BY h.code ORDER BY h.date DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS latest_close,
    #         MAX(h.date)  AS latest_date
    #     FROM history h
    #     {where}
    #     GROUP BY h.code
    #     ORDER BY h.code
    #     LIMIT :limit OFFSET :offset
    # """)
    count_sql = text("SELECT COUNT(DISTINCT code) FROM history")
    list_sql = text("""
        SELECT
            h.code,
            h.name,
            h.close AS latest_close,
            h.date AS latest_date
        FROM history h
        LEFT JOIN history h2
            ON h.code = h2.code
        AND h.date < h2.date
        WHERE h2.code IS NULL
        ORDER BY h.code
        LIMIT :limit OFFSET :offset;
        """)

    params = {"limit": page_size, "offset": offset}
    # if keyword:
    #     params["kw"] = kw

    with db as session:
        total  = session.execute(count_sql, params).scalar() or 0
        rows   = session.execute(list_sql, params).fetchall()

    stocks = []
    for r in rows:
        code        = r[0]
        name        = r[1] or ""
        step_status = _get_step_status_for_code(db, code)
        stocks.append({
            "code":         code,
            "name":         name,
            "latest_close": r[2],
            "latest_date":  r[3],
            "step_status":  step_status,
            "links":        _make_links(code, name),
        })

    return {"total": total, "page": page, "page_size": page_size, "items": stocks}

@redis_cache(
    prefix="stock_code_status",
    key="{code}",
    ttl=1800,
)
def _get_step_status_for_code(db: Session, code: str) -> dict:
    """查询单股各 step 最新状态"""
    sql = text("""
        SELECT code, step, completed_at
        FROM etl_code_checkpoint
        WHERE code = :code
    """)
    rows   = db.execute(sql, {"code": code}).fetchall()
    result = {}
    for r in rows:
        result[r[1]] = r[2]

    return result


def get_stock_detail(db: Session, code: str) -> dict:
    """获取单股详细数据：profile + OHLC + 新闻 + 财务"""

    # profile
    profile = db.execute(
        text("SELECT * FROM stock_profile WHERE code = :code LIMIT 1"),
        {"code": code}
    ).mappings().fetchone()

    # OHLC 最近 60 条
    ohlc = db.execute(
        text("""
            SELECT date, open, high, low, close, volume, price_change
            FROM history WHERE CAST(code AS CHAR) = :code
            ORDER BY date DESC LIMIT 60
        """),
        {"code": code}
    ).mappings().fetchall()

    # 新闻 最近 20 条
    news = db.execute(
        text("""
            SELECT id, title, content, mediaName, url, date
            FROM stock_news WHERE code = :code
            ORDER BY date DESC LIMIT 20
        """),
        {"code": code}
    ).mappings().fetchall()

    # 财务报表 最近 8 条
    financial = db.execute(
        text("""
            SELECT report_date, revenue, net_profit, eps, roe
            FROM financial_statement WHERE code = :code
            ORDER BY report_date DESC LIMIT 8
        """),
        {"code": code}
    ).mappings().fetchall()

    name = profile["name"] if profile and "name" in profile else ""

    return {
        "code":      code,
        "name":      name,
        "profile":   dict(profile)   if profile   else None,
        "ohlc":      [dict(r) for r in ohlc],
        "news":      [dict(r) for r in news],
        "financial": [dict(r) for r in financial],
        "links":     _make_links(code, name),
    }


def get_all_step_status(db: Session) -> List[dict]:
    """全局 step 状态概览（用于总开关页面）"""
    sql = text("""
        SELECT
            step,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN status = 'failed'  THEN 1 ELSE 0 END) AS failed_count,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_count,
            MAX(finished_at) AS last_finished,
            MAX(row_count)   AS last_row_count
        FROM etl_job_log
        GROUP BY step
        ORDER BY step
    """)
    rows = db.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]