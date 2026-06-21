"""sources/financial_statement.py — 财务报表抓取（akshare 抽象财务指标，宽表转长表）"""
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
    """akshare 返回的宽表（指标 x 日期）转为长表（code, report_date, metric...）"""
    date_cols = [c for c in df.columns if c not in ("选项", "指标")]
    result: dict[tuple[str, str], dict] = {}
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


def fetch_financial_statements(start_code: int = 0, end_code: int = 1000000) -> pd.DataFrame:
    """逐只股票抓取财务摘要并转换为标准长表，附带限流和容错"""
    codes = [(r["code"], r["name"]) for r in ak.stock_info_a_code_name().to_dict("records")]
    codes = [(add_prefix(c[0]), c[1]) for c in codes if start_code <= int(c[0]) <= end_code]

    frames = []
    for code, name in codes:
        try:
            raw = ak.stock_financial_abstract(symbol=code)
        except Exception as e:
            logger.error("[FETCH ERROR] {}: {}", code, e)
            time.sleep(120)
            continue
        df = transform_wide(raw, code)
        df["name"] = name
        frames.append(df)
        logger.info("fetched {} {}", code, name)
        time.sleep(random.uniform(2, 3))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
