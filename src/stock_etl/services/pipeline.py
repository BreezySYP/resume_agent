"""pipeline.py — ETL 总入口

用法（cwd 需为 src/stock_etl）:
    uv run python pipeline.py --steps history,technical,composite
    uv run python pipeline.py --steps all
"""
import argparse
import datetime

import pandas as pd
from factors.composite import build_composite_factor
from factors.financial_factor import build_financial_factor
from factors.financial_feature import build_financial_features
from factors.technical import build_technical_factor
from loguru import logger
from shared.db.mysql import engine
from shared.text.stock_text import (build_stock_news_text, build_stock_profile_text,
                                     get_stock_news_payload, get_stock_profile_payload)
from sources import capital_and_hot
from data_loader import load_df
from sources import financial_statement, history, news, profile
from storage import mysql_writer, qdrant_writer
from storage import step_checkpoint
from sqlalchemy import text
from trading_calendar import next_trading_day

QDRANT_NEWS_COLLECTION = "stock_news_hybrid"
QDRANT_PROFILE_COLLECTION = "stock_profile_hybrid"
TECHNICAL_WINDOW_DAYS = 180   # MA120 需要的最小历史窗口
DEFAULT_START_DATE = "2025-01-01"


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


# ── history ────────────────────────────────────────────────────────────────────

def run_history_step(start_date: str | None = None, end_date: str | None = None) -> None:
    cp = step_checkpoint.get_checkpoint("history")
    effective_start = cp.last_completed_date if cp.last_completed_date else DEFAULT_START_DATE
    effective_end =  end_date or today()
    resume_code = cp.start_code or "000000"
    logger.info("history: start={}, end={}, resume_code={}", effective_start, effective_end, resume_code)

    def on_batch(df: pd.DataFrame, last_code: str) -> None:
        mysql_writer.save_history(df)
        step_checkpoint.save_checkpoint("history", start_code=last_code)

    history.fetch_all_history(effective_start, next_trading_day(effective_end), min_code=resume_code, on_batch=on_batch)
    # checkpoint.save_checkpoint("history", start_date=effective_end)


# ── technical ──────────────────────────────────────────────────────────────────

def run_technical_step() -> None:
    cp = step_checkpoint.get_checkpoint("technical")
    new_start = cp.last_completed_date or DEFAULT_START_DATE
    start_code = '000001' or cp.start_code
    logger.info("technical: 增量计算 date > {} code > {}", new_start, start_code)

    records = [(r["code"].zfill(6), r["name"]) for r in  history.get_all_codes().to_dict("records") if r["code"] >= start_code]
    for code, name in records:
        sql = f"select * from history where code = '{code}'"
        df = load_df(sql, "history")
        if df.empty:
            logger.info("technical: 无新数据，跳过")
            return 

        df["date"] = pd.to_datetime(df["date"])
        factor_df = build_technical_factor(df)

        # 只保存新日期的结果，旧日期已在库中
        new_rows = factor_df[factor_df["date"] > pd.to_datetime(new_start)]
        if new_rows.empty:
            logger.info("technical: 计算完成但无新日期结果")
            return
        step_checkpoint.save_checkpoint("technical", start_code=code)
        mysql_writer.save_technical_factor(new_rows)


# ── financial_feature ──────────────────────────────────────────────────────────

def run_financial_feature_step() -> None:
    cp = step_checkpoint.get_checkpoint("financial_feature")
    last_at = cp.last_completed_at or datetime.datetime(2000, 1, 1)
    logger.info("financial_feature: 增量处理 updated_at > {}", last_at)

    df = load_df(f"SELECT * FROM financial_statement WHERE report_date > {last_at}", "financial_statement")
    if df.empty:
        logger.info("financial_feature: 无新数据，跳过")
        return
    df["report_date"] = pd.to_datetime(df["report_date"])
    mysql_writer.save_financial_feature(build_financial_features(df))


# ── financial_factor ───────────────────────────────────────────────────────────

def run_financial_factor_step() -> None:
    cp = step_checkpoint.get_checkpoint("financial_factor")
    last_at = cp.last_completed_at or datetime.datetime(2000, 1, 1)
    logger.info("financial_factor: 增量处理 updated_at > {}", last_at)

    df = load_df( f"SELECT * FROM financial_feature WHERE report_date > {last_at}", "financial_feature")
    if df.empty:
        logger.info("financial_factor: 无新数据，跳过")
        return
    df["report_date"] = pd.to_datetime(df["report_date"])
    mysql_writer.save_financial_factor(build_financial_factor(df))


# ── composite ──────────────────────────────────────────────────────────────────

def run_composite_step(horizon: str = "medium") -> None:
    cp = step_checkpoint.get_checkpoint("composite")
    new_start = cp.last_completed_date or DEFAULT_START_DATE
    logger.info("composite: 增量计算 date > {}", new_start)

    # 只取新的技术因子日期
    technical_df = load_df(f"SELECT * FROM technical_factor WHERE date > {new_start} ORDER BY code, date", "technical_factor")

    if technical_df.empty:
        logger.info("composite: 无新技术因子，跳过")
        return
    technical_df["date"] = pd.to_datetime(technical_df["date"])

    # 财务因子取全量（merge_asof 需要完整的历史财务序列）
    financial_df = load_df("SELECT * FROM financial_factor ORDER BY code, report_date", "financial_factor",)
    financial_df["report_date"] = pd.to_datetime(financial_df["report_date"])

    factor_df = build_composite_factor(technical_df, financial_df, horizon=horizon)
    mysql_writer.save_stock_factor(factor_df)


# ── capital & hot ──────────────────────────────────────────────────────────────

def run_capital_and_hot_step() -> None:
    # 实时接口，每次全量拉取当日数据，无需增量
    hot_df = capital_and_hot.fetch_hot_sectors()
    if hot_df is not None:
        mysql_writer.save_hot_sectors(hot_df)
    flow_df = capital_and_hot.fetch_capital_flow()
    if flow_df is not None:
        mysql_writer.save_capital_flow(flow_df)


# ── financial_statement ────────────────────────────────────────────────────────

def run_financial_statement_step(start_code: int = 0, end_code: int = 1000000) -> None:
    cp = step_checkpoint.get_checkpoint("financial_statement")
    resume_code = max(start_code, int(cp.start_code)) if cp.start_code else start_code
    logger.info("financial_statement: resume_code={}", resume_code)

    def on_batch(df: pd.DataFrame, last_code: str) -> None:
        mysql_writer.save_financial_statement(df)
        step_checkpoint.save_checkpoint("financial_statement", start_code=last_code)

    financial_statement.fetch_financial_statements(resume_code, end_code, on_batch=on_batch)


# ── profile ────────────────────────────────────────────────────────────────────

def run_profile_step(min_code: str = "000000") -> None:
    cp = step_checkpoint.get_checkpoint("profile")
    resume_code = max(min_code, cp.start_code) if cp.start_code else min_code
    logger.info("profile: resume_code={}", resume_code)

    def on_batch(profile_df: pd.DataFrame, breakdown_df: pd.DataFrame, last_code: str) -> None:
        if not profile_df.empty:
            mysql_writer.save_stock_profile(profile_df)
        if not breakdown_df.empty:
            mysql_writer.save_stock_business_breakdown(breakdown_df)
        step_checkpoint.save_checkpoint("profile", start_code=last_code)

    profile.fetch_profiles_and_breakdowns(resume_code, on_batch=on_batch)


# ── news ───────────────────────────────────────────────────────────────────────

def run_news_step(min_code: str = "000000") -> None:
    cp = step_checkpoint.get_checkpoint("news")
    resume_code = max(min_code, cp.start_code) if cp.start_code else min_code
    logger.info("news: resume_code={}", resume_code)

    def on_batch(df: pd.DataFrame, last_code: str) -> None:
        mysql_writer.save_stock_news(df)
        step_checkpoint.save_checkpoint("news", start_code=last_code)

    news.fetch_all_stock_news(resume_code, on_batch=on_batch)
    


# ── qdrant sync ────────────────────────────────────────────────────────────────

def run_news_qdrant_sync_step() -> None:
    cp = step_checkpoint.get_checkpoint("qdrant_sync")
    last_at = cp.last_completed_at or datetime.datetime(2000, 1, 1)
    logger.info("qdrant_sync: 增量同步 updated_at > {}", last_at)

    news_df = load_df(f"SELECT * FROM stock_news WHERE date > '{last_at}'","stock_news")
    if not news_df.empty:
        qdrant_writer.upsert_hybrid(news_df, QDRANT_NEWS_COLLECTION, build_stock_news_text, get_stock_news_payload)

def run_profile_qdrant_sync_step() -> None:
    cp = step_checkpoint.get_checkpoint("qdrant_sync")
    last_at = cp.last_completed_at or datetime.datetime(2000, 1, 1)
    logger.info("qdrant_sync: 增量同步 updated_at > {}", last_at)

    profile_df = load_df(f"SELECT * FROM stock_profile WHERE update_time > '{last_at}'","stock_profile")
    if not profile_df.empty:
        qdrant_writer.upsert_hybrid(profile_df, QDRANT_PROFILE_COLLECTION, build_stock_profile_text, get_stock_profile_payload)


# ── pipeline ───────────────────────────────────────────────────────────────────

STEPS = {
    "history":               run_history_step,
    "technical":             run_technical_step,
    "financial_statement":   run_financial_statement_step,
    "financial_feature":     run_financial_feature_step,
    "financial_factor":      run_financial_factor_step,
    "composite":             run_composite_step,
    "capital_hot":           run_capital_and_hot_step,
    "profile":               run_profile_step,
    "news":                  run_news_step,
    "qdrant_news_sync":           run_news_qdrant_sync_step,
    "qdrant_profile_sync":           run_profile_qdrant_sync_step,
}

DEFAULT_DAILY_STEPS = ["history", "technical", "capital_hot", "news", "qdrant_news_sync"]
DEFAULT_SEASON_STEPS = ["history", "technical", "financial_statement", "financial_feature",
                         "financial_factor", "composite", "capital_hot", "profile", "news", "qdrant_profile_sync", "qdrant_news_sync"]

def run_pipeline(steps: list[str]) -> None:
    for step in steps:
        if step not in STEPS:
            logger.warning("跳过未知 step: {}", step)
            continue
        if step_checkpoint.is_completed_today(step):
            logger.info("⏭️  skip {} (今天已完成)", step)
            continue
        logger.info("=== start: {} ===", step)
        try:
            STEPS[step]()
        except Exception as e:
            logger.error("❌ {} 失败: {}，下次从断点继续", step, e)
            raise
        step_checkpoint.mark_completed(step)
        logger.success("=== done: {} ===", step)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock ETL pipeline")
    parser.add_argument(
        "--steps", default=",".join(DEFAULT_DAILY_STEPS),
        help=f"逗号分隔，可选: {','.join(STEPS)} 或 all",
    )
    args = parser.parse_args()
    steps = list(STEPS) if args.steps == "all" else [s.strip() for s in args.steps.split(",") if s.strip()]
    run_pipeline(steps)


if __name__ == "__main__":
    # main()
    run_pipeline(["technical"])