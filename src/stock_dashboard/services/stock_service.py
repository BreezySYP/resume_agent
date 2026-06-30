"""services/stock_service.py — 股票数据查询"""
from __future__ import annotations
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger


STOCK_STEPS = ["history", "financial_statement", "profile", "news", "technical"]


def _make_links(code: str, name: str) -> dict:
    # 判断前缀
    prefix = "SH" if code.startswith("6") else "SZ"
    return {
        "eastmoney":    f"https://quote.eastmoney.com/concept/{code}.html",
        "xueqiu":       f"https://xueqiu.com/S/{prefix}{code}",
        "tonghuashun":  f"https://stockpage.10jqka.com.cn/{code}/",
    }


def get_stock_list(db: Session, page: int = 1, page_size: int = 50, keyword: str = "") -> dict:
    """
    从 history 表 distinct 获取股票列表，附带最新收盘价和各 step 最新状态。
    """
    offset = (page - 1) * page_size

    # 基础列表
    where = "WHERE CA
    
    count_sql = text(f"""
        SELECT COUNT(DISTINCT code) FROM history {where}
    """)
    list_sql = text(f"""
        SELECT
            CAST(h.code AS CHAR)  AS code,
            MAX(CAST(h.name AS CHAR)) AS name,
            MAX(h.close) OVER (PARTITION BY h.code ORDER BY h.date DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS latest_close,
            MAX(h.date)  AS latest_date
        FROM history h
        {where}
        GROUP BY h.code
        ORDER BY h.code
        LIMIT :limit OFFSET :offset
    """)

    params = {"limit": page_size, "offset": offset}
    if keyword:
        params["kw"] = kw

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


def _get_step_status_for_code(db: Session, code: str) -> dict:
    """查询单股各 step 最新状态"""
    sql = text("""
        SELECT step, status, finished_at, row_count, error_msg
        FROM etl_job_log
        WHERE code = :code
          AND id IN (
              SELECT MAX(id) FROM etl_job_log WHERE code = :code GROUP BY step
          )
    """)
    rows   = db.execute(sql, {"code": code}).fetchall()
    result = {}
    for r in rows:
        result[r[0]] = {
            "step":         r[0],
            "status":       r[1],
            "last_success": r[2],
            "row_count":    r[3] or 0,
            "error_msg":    r[4],
        }
    # 补全没有记录的 step
    for step in STOCK_STEPS:
        if step not in result:
            result[step] = {"step": step, "status": None, "last_success": None, "row_count": 0, "error_msg": None}
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
            SELECT id, title, content, source, url, date
            FROM stock_news WHERE code = :code
            ORDER BY date DESC LIMIT 20
        """),
        {"code": code}
    ).mappings().fetchall()

    # 财务报表 最近 8 条
    financial = db.execute(
        text("""
            SELECT report_date, revenue, net_profit, eps, roe, report_type
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