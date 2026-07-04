"""sources/financial_statement.py — 财务报表抓取"""
import random
import time

import akshare as ak
import pandas as pd
from loguru import logger
from shared.code_rule import add_prefix

FINANCIAL_METRIC_MAP = {
    "归母净利润": "net_profit", "营业总收入": "revenue", "经营现金流量净额": "operating_cashflow",
    "净资产收益率(ROE)": "roe", "资产负债率": "asset_liability_ratio", "扣非净利润": "deduct_net_profit",
    "毛利率": "gross_margin", "销售净利率": "net_margin", "营业收入增长率": "revenue_growth",
    "归属母公司净利润增长率": "profit_growth", "总资产报酬率(ROA)": "roa", "每股收益": "eps",
    "每股净资产": "bvps", "每股经营现金流": "ocfps",
}


def transform_wide(df: pd.DataFrame, code: str) -> pd.DataFrame:
    date_cols = [c for c in df.columns if c not in ("选项", "指标")]
    result: dict[tuple, dict] = {}
    for _, row in df.iterrows():
        metric = row["指标"]
        if metric not in FINANCIAL_METRIC_MAP:
            continue
        col_name = FINANCIAL_METRIC_MAP[metric]
        for d in date_cols:
            value = row[d]
            if pd.isna(value):
                continue
            result.setdefault((code, d), {})[col_name] = float(value)
    return pd.DataFrame([{"code": code, "report_date": date, **values} for (code, date), values in result.items()])


def fetch_financial_statement(code, name):
    raw = ak.stock_financial_abstract(symbol=code)
    df = transform_wide(raw, code)
    df["name"] = name
    logger.info("fetched {} {}", code, name)
    return df

def fetch_financial_statements(start_code: int = 0, end_code: int = 1000000, on_batch=None, batch_size: int = 50) -> None:
    """逐批抓取财务摘要。每 batch_size 只股票后调用 on_batch(df, last_code)：
    调用方负责在 on_batch 里先存 DB 再更新 checkpoint。
    """
    codes = [(r["code"], r["name"]) for r in ak.stock_info_a_code_name().to_dict("records")]
    codes = [(add_prefix(c[0]), c[1]) for c in codes if start_code <= int(c[0]) <= end_code]

    frames = []
    last_code = None
    for code, name in codes:
        try:
            df = fetch_financial_statement(code, name)
        except Exception as e:
            logger.error("[FETCH ERROR] {}: {}", code, e)
            time.sleep(120)
            continue
        frames.append(df)
        if on_batch and len(frames) >= batch_size and last_code:
            on_batch(pd.concat(frames, ignore_index=True), last_code)
            frames = []

        time.sleep(random.uniform(2, 3))

    if on_batch and frames and last_code:
        on_batch(pd.concat(frames, ignore_index=True), last_code)