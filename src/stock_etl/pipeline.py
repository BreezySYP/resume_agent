"""pipeline.py — ETL 总入口：拉取每日行情 -> 计算因子 -> 写入 MySQL / Qdrant

用法:
    uv run python -m stock_etl.pipeline --steps history,technical,composite
    uv run python -m stock_etl.pipeline --steps all
"""
import argparse
import datetime

import pandas as pd
from data_loader import load_df
from factors.composite import build_composite_factor
from factors.financial_factor import build_financial_factor
from factors.financial_feature import build_financial_features
from factors.technical import build_technical_factor
from loguru import logger
from shared.db.mysql import engine
from shared.text.stock_text import build_stock_news_text, build_stock_profile_text, get_stock_news_payload, get_stock_profile_payload
from sources import capital_and_hot, financial_statement, history, news, profile
from storage import mysql_writer, qdrant_writer

QDRANT_NEWS_COLLECTION = "stock_news_hybrid"
QDRANT_PROFILE_COLLECTION = "stock_profile_hybrid"


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def load_price_and_valuation() -> pd.DataFrame:
    """加载价格和估值数据；估值列暂为占位，待接入真实 PE/PB 数据源后替换"""
    sql = "SELECT h.code, h.date, h.close, NULL as pe_ttm, NULL as pb, NULL as peg FROM history h"
    return load_df(sql, "history")


def run_history_step(start_date: str = "2025-01-01", end_date: str | None = None) -> None:
    """拉取全市场历史行情并入库"""
    df = history.fetch_all_history(start_date, end_date or today())
    if not df.empty:
        mysql_writer.save_history(df)


def run_technical_step() -> pd.DataFrame:
    """计算技术因子并写入 technical_factor 表"""
    df = pd.read_sql("SELECT code, name, date, open, high, low, close, volume FROM history", engine)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    factor_df = build_technical_factor(df)
    mysql_writer.save_technical_factor(factor_df)
    return factor_df


def run_financial_feature_step() -> pd.DataFrame:
    """从 financial_statement 计算特征并写入 financial_feature 表"""
    df = pd.read_sql("SELECT * FROM financial_statement", engine)
    df["report_date"] = pd.to_datetime(df["report_date"])
    feature_df = build_financial_features(df)
    mysql_writer.save_financial_feature(feature_df)
    return feature_df


def run_financial_factor_step() -> pd.DataFrame:
    """从 financial_feature 计算财务因子并写入 financial_factor 表"""
    df = pd.read_sql("SELECT * FROM financial_feature", engine)
    df["date"] = pd.to_datetime(df["report_date"])
    factor_df = build_financial_factor(df)
    mysql_writer.save_financial_factor(factor_df)
    return factor_df


def run_composite_step(horizon: str = "medium") -> pd.DataFrame:
    """合并技术面/财务面/估值面，写入 stock_factor 表"""
    technical_df = load_df("SELECT * FROM technical_factor", "technical_factor")
    financial_df = load_df("SELECT * FROM financial_factor", "financial_factor")
    price_valuation_df = load_price_and_valuation()
    factor_df = build_composite_factor(technical_df, financial_df, price_valuation_df, horizon=horizon)
    mysql_writer.save_stock_factor(factor_df)
    return factor_df


def run_capital_and_hot_step() -> None:
    """抓取主力资金流 + 热门板块并入库"""
    hot_df = capital_and_hot.fetch_hot_sectors()
    if hot_df is not None:
        mysql_writer.save_hot_sectors(hot_df)
    flow_df = capital_and_hot.fetch_capital_flow()
    if flow_df is not None:
        mysql_writer.save_capital_flow(flow_df)


def run_financial_statement_step(start_code: int = 0, end_code: int = 1000000) -> None:
    """抓取财报原始数据并入库（低频，建议季度跑一次）"""
    df = financial_statement.fetch_financial_statements(start_code, end_code)
    if not df.empty:
        mysql_writer.save_financial_statement(df)


def run_profile_step(min_code: str = "000000") -> None:
    """抓取主营业务简介 + 主营构成并入库（低频）"""
    profile_df, breakdown_df = profile.fetch_profiles_and_breakdowns(min_code)
    if not profile_df.empty:
        mysql_writer.save_stock_profile(profile_df)
    if not breakdown_df.empty:
        mysql_writer.save_stock_business_breakdown(breakdown_df)


def run_news_step(min_code: str = "000000") -> None:
    """抓取个股新闻并入库"""
    df = news.fetch_all_stock_news(min_code)
    if not df.empty:
        mysql_writer.save_stock_news(df)


def run_qdrant_sync_step() -> None:
    """把 MySQL 中的新闻 / 主营业务画像同步到 Qdrant 向量库，供 Agent 检索"""
    news_df = load_df("SELECT * FROM stock_news", "stock_news")
    qdrant_writer.upsert_hybrid(news_df, QDRANT_NEWS_COLLECTION, build_stock_news_text, get_stock_news_payload)

    profile_df = load_df("SELECT * FROM stock_profile", "stock_profile")
    qdrant_writer.upsert_hybrid(profile_df, QDRANT_PROFILE_COLLECTION, build_stock_profile_text, get_stock_profile_payload)


STEPS = {
    "history": run_history_step,
    "technical": run_technical_step,
    "financial_feature": run_financial_feature_step,
    "financial_factor": run_financial_factor_step,
    "composite": run_composite_step,
    "capital_hot": run_capital_and_hot_step,
    "financial_statement": run_financial_statement_step,
    "profile": run_profile_step,
    "news": run_news_step,
    "qdrant_sync": run_qdrant_sync_step,
}

# 每日例行：拉取最新行情 -> 技术因子 -> 综合因子（财务/资讯类数据频率较低，按需单独运行）
DEFAULT_DAILY_STEPS = ["history", "technical", "composite"]


def run_pipeline(steps: list[str]) -> None:
    for step in steps:
        if step not in STEPS:
            logger.warning("跳过未知 step: {}", step)
            continue
        logger.info("=== running step: {} ===", step)
        STEPS[step]()
        logger.success("=== step done: {} ===", step)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock ETL pipeline")
    parser.add_argument("--steps", default=",".join(DEFAULT_DAILY_STEPS), help=f"逗号分隔的步骤，可选: {','.join(STEPS)} 或 all")
    args = parser.parse_args()
    steps = list(STEPS) if args.steps == "all" else [s.strip() for s in args.steps.split(",") if s.strip()]
    run_pipeline(steps)


if __name__ == "__main__":
    main()
