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
from shared.code_rule import add_prefix
from shared.db.mysql import engine, execute_query
from shared.text.stock_text import (build_stock_news_text, build_stock_profile_text,
                                     get_stock_news_payload, get_stock_profile_payload)
from sources import capital_and_hot
from data_loader import load_df
from sources import financial_statement, history, news, profile
from storage import code_checkpoint, mysql_writer, qdrant_writer
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

def run_history_step(code :str, name: str, start_date ) -> None:
    """code 格式是 000001"""
    end_date: str=today()
    # records = execute_query(f"select max(date) as date from history where code = '{code}'")
    # start_date = records[0]["date"].strftime("%Y-%m-%d")
    logger.info("history: start={}, end={}, code={}", start_date, end_date, code)
    df = history.fetch_history(name, code, start_date, next_trading_day(end_date))
    if df.empty:
        logger.info("history: 无新数据，跳过")
        return
    mysql_writer.save_history(df)



# ── composite ──────────────────────────────────────────────────────────────────

def run_composite_step(horizon: str = "medium") -> None:
    cp = step_checkpoint.get_checkpoint("composite")
    new_start = cp.last_completed_date or DEFAULT_START_DATE
    logger.info("composite: 增量计算 date > {}", new_start)

    # 只取新的技术因子日期
    technical_df = load_df(f"SELECT * FROM technical_factor WHERE date >= {new_start} ORDER BY code, date", "technical_factor")

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

def run_financial_statement_step(code, name, start_date) -> None:
    """code 格式为 sz000001"""
    code = add_prefix(code)
    logger.info("financial_statement: code={} name={}", code, name)
    df = financial_statement.fetch_financial_statement(code, name)
    if df.empty:
        logger.info("financial_statement: 无新数据，跳过")
        return
    mysql_writer.save_financial_statement(df)


# ── financial_feature ──────────────────────────────────────────────────────────

def run_financial_feature_step(code, name, start_date) -> None:
    """code 格式为 sz000001"""
    code = add_prefix(code)
    logger.info("financial_feature: 增量处理 code:{} name: {}", code, name)
    df = pd.read_sql(f"SELECT * FROM financial_statement WHERE report_date >= {start_date} and code = {code}", con=engine.connect())
    if df.empty:
        logger.info("financial_feature: 无新数据，跳过")
        return
    df["report_date"] = pd.to_datetime(df["report_date"])
    mysql_writer.save_financial_feature(build_financial_features(df))

# ── profile ────────────────────────────────────────────────────────────────────

def run_profile_step(code, name, start_date) -> None:
    """code 格式是 000001"""
    logger.info("profile: code={} name={}", code, name)
    df = profile.fetch_profile(code, name)
    if df.empty:
        logger.info("profile: 无新数据，跳过")
    else:
        mysql_writer.save_stock_profile(df)
        profile_df = pd.read_sql(f"SELECT * FROM stock_profile WHERE code = {code} AND update_time >= '{start_date}'", con=engine.connect())
        qdrant_writer.upsert_hybrid(profile_df, QDRANT_PROFILE_COLLECTION, build_stock_profile_text, get_stock_profile_payload)
    df = profile.fetch_news_breakdown(code, name)
    if df.empty:
        logger.info("fetch_news_breakdown: 无新数据，跳过")
        return
    mysql_writer.save_stock_business_breakdown(df)

# ── news ───────────────────────────────────────────────────────────────────────

def run_news_step(code, name, start_date) -> None:
    """code format is 000001"""
    logger.info("add news for code {} name {}", code, name)

    df = news.fetch_stock_news(code, name)
    if df.empty:
        logger.info("fetch_stock_news: 无新数据，跳过")
        return 

    mysql_writer.save_stock_news(df)
    news_df = pd.read_sql(f"SELECT * FROM stock_news WHERE code = {code} AND fetch_time >= '{start_date}'", con=engine.connect())
    qdrant_writer.upsert_hybrid(news_df, QDRANT_NEWS_COLLECTION, build_stock_news_text, get_stock_news_payload)
    


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

# ── pipeline ───────────────────────────────────────────────────────────────────

CODE_BY_CODE_STEPS = {
    "history":               run_history_step,
    "financial_statement":   run_financial_statement_step,
    "financial_feature":     run_financial_feature_step,
    "profile":               run_profile_step,
    "news":                  run_news_step,
}

ALL_TOGETHER_STEPS = {
    "capital_hot":           run_capital_and_hot_step,
    "technical":             run_technical_step,
    "financial_factor":      run_financial_factor_step,
    "composite":             run_composite_step,
}

DEFAULT_DAILY_STEPS = ["history", "technical", "capital_hot", "news", "qdrant_news_sync"]
DEFAULT_SEASON_STEPS = ["history", "technical", "financial_statement", "financial_feature",
                         "financial_factor", "composite", "capital_hot", "profile", "news", "qdrant_profile_sync", "qdrant_news_sync"]

def get_codes():
    code_names = {r["code"]: r["name"] for r in history.get_all_codes().to_dict("records")}
    df_checkpoint = pd.read_sql("SELECT * FROM etl_code_checkpoint", con=engine.connect())
    code_group = df_checkpoint.groupby("code")
    result = []
    now = datetime.datetime.now()
    
    for code in code_names.keys():
        # 检查这个code是否有checkpoint记录
        if code not in code_group.groups:
            # 如果没有记录，说明从未运行过，需要处理
            result.append((code, code_names[code]))
            continue
        
        # 获取该code的所有记录
        group_data = code_group.get_group(code)
        
        # 检查是否所有记录的 complete_at 的下一个8点都大于 now
        # 如果是，说明所有任务都还没到下一个8点，跳过
        all_future = all(
            code_checkpoint.get_next_8am(pd.to_datetime(row.completed_at, unit='s')) > now 
            for _, row in group_data.iterrows()
        )
        
        if all_future:
            # 所有记录的下一个8点都在未来，暂时不需要处理
            continue
        
        # 否则，至少有一条记录的下一个8点已到或已过，需要处理
        result.append((code, code_names[code]))
    
    return result


def run_code_pipeline(code, steps: list[str]) -> None:
    name = get_name(code)
    for step in steps:
            start_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if step not in CODE_BY_CODE_STEPS:
                logger.warning("跳过未知 step: {}", step)
                continue
            if code_checkpoint.is_completed_today(code, step):
                logger.info("⏭️  skip {} {} (今天已完成)", code, step)
                continue
            logger.info("=== start: {} ===", step)
            try:
                CODE_BY_CODE_STEPS[step](code, name, start_at)
            except Exception as e:
                logger.error("❌ {} 失败: {}，下次从断点继续", step, e)
                raise
            code_checkpoint.save_checkpoint(code, step, start_at)
            logger.success("=== done: {} for code {} name {} ===", step, code, name)


def run_pipeline(steps: list[str]) -> None:
    
    for code, name in get_codes():
        for step in steps:
            start_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if step not in CODE_BY_CODE_STEPS:
                logger.warning("跳过未知 step: {}", step)
                continue
            if code_checkpoint.is_completed_today(code, step):
                logger.info("⏭️  skip {} {} (今天已完成)", code, step)
                continue
            logger.info("=== start: {} ===", step)
            try:
                CODE_BY_CODE_STEPS[step](code, name, start_at)
            except Exception as e:
                logger.error("❌ {} 失败: {}，下次从断点继续", step, e)
                raise
            code_checkpoint.save_checkpoint(code, step, start_at)
            logger.success("=== done: {} for code {} name {} ===", step, code, name)

def get_name(code: str):
    with engine.begin() as db:
        query = db.execute(text("SELECT name FROM history WHERE code = :code"), {"code": code})
        result = query.fetchone()
        return result[0]

def main() -> None:
    parser = argparse.ArgumentParser(description="Stock ETL pipeline")
    parser.add_argument(
        "--steps", default=",".join(DEFAULT_DAILY_STEPS),
        help=f"逗号分隔，可选: {','.join(STEPS)} 或 all",
    )
    args = parser.parse_args()
    steps = list(CODE_BY_CODE_STEPS) if args.steps == "all" else [s.strip() for s in args.steps.split(",") if s.strip()]
    run_pipeline(steps)


if __name__ == "__main__":
    # main()
    # print(get_codes())
    print(get_name("000001"))
    # run_pipeline(["history", "profile", "news"])