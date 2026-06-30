"""routers/stocks.py — 股票列表 & 详情 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from loguru import logger

from stock_dashboard.db import get_db
from stock_dashboard.services.stock_service import (
    get_stock_list,
    get_stock_detail,
    get_all_step_status,
)

router = APIRouter(prefix="/api/stocks", tags=["股票数据"])


@router.get(
    "",
    summary="获取股票列表",
    description="""
        从 history 表获取所有股票（distinct code），每行包含：
        - 基础信息（code、name、最新收盘价、最新日期）
        - 各 ETL step 的最新执行状态
        - 东方财富 / 雪球 / 同花顺 链接
            """,
)
def list_stocks(
    page:      int = Query(1,   ge=1,  description="页码，从 1 开始"),
    page_size: int = Query(50,  ge=1, le=200, description="每页数量"),
    keyword:   str = Query("",        description="按代码或名称模糊搜索"),
    db:        Session = Depends(get_db),
):
    return get_stock_list(db, page=page, page_size=page_size, keyword=keyword)


@router.get(
    "/{code}",
    summary="获取单股详情",
    description="""
返回单只股票的完整数据：
- 公司简介（stock_profile）
- 最近 60 条 OHLC K线数据（history）
- 最近 20 条新闻（stock_news）
- 最近 8 期财务报表（financial_statement）
- 东方财富 / 雪球 / 同花顺 链接
    """,
)
def stock_detail(
    code: str,
    db:   Session = Depends(get_db),
):
    return get_stock_detail(db, code)


@router.get(
    "/status/overview",
    summary="全局 ETL step 状态概览",
    description="按 step 汇总所有股票的执行成功/失败/运行中数量，用于总开关页面。",
)
def step_status_overview(db: Session = Depends(get_db)):
    return get_all_step_status(db)