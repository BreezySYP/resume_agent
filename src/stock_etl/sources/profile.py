"""sources/profile.py — 个股主营业务简介 + 主营构成抓取（东方财富 / 同花顺）"""
import random
import time
from datetime import datetime

import akshare as ak
import pandas as pd
import requests
from loguru import logger
from shared.code_rule import add_prefix

ZYGC_RENAME = {
    "SECURITY_CODE": "股票代码", "REPORT_DATE": "报告日期", "MAINOP_TYPE": "分类类型", "ITEM_NAME": "主营构成",
    "MAIN_BUSINESS_INCOME": "主营收入", "MBI_RATIO": "收入比例", "MAIN_BUSINESS_COST": "主营成本",
    "MBC_RATIO": "成本比例", "MAIN_BUSINESS_RPOFIT": "主营利润", "MBR_RATIO": "利润比例", "GROSS_RPOFIT_RATIO": "毛利率",
}
ZYGC_COLS = ["股票代码", "报告日期", "分类类型", "主营构成", "主营收入", "收入比例", "主营成本", "成本比例", "主营利润", "利润比例", "毛利率"]
ZYGC_TYPE_MAP = {"1": "按行业分类", "2": "按产品分类", "3": "按地区分类"}
BREAKDOWN_RENAME = {
    "股票代码": "code", "报告日期": "report_date", "分类类型": "category_type", "主营构成": "category_name",
    "主营收入": "revenue", "收入比例": "revenue_ratio", "主营成本": "cost", "成本比例": "cost_ratio",
    "主营利润": "profit", "利润比例": "profit_ratio", "毛利率": "gross_margin",
}


def stock_zygc_em(symbol: str = "SH688041") -> pd.DataFrame:
    """东方财富网-个股-主营构成"""
    r = requests.get("https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax", params={"code": symbol})
    data_json = r.json()
    if data_json.get("status", 0) < 0:
        logger.error("error call for {} {}", symbol, data_json)
        return pd.DataFrame()
    df = pd.DataFrame(data_json["zygcfx"])
    if df.empty:
        return df
    df = df.rename(columns=ZYGC_RENAME)[ZYGC_COLS]
    df["报告日期"] = pd.to_datetime(df["报告日期"], errors="coerce").dt.date
    df["分类类型"] = df["分类类型"].map(ZYGC_TYPE_MAP)
    for col in ("主营收入", "收入比例", "主营成本", "成本比例", "主营利润", "利润比例", "毛利率"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch_profiles_and_breakdowns(min_code: str = "000000") -> tuple[pd.DataFrame, pd.DataFrame]:
    """抓取全市场（或起始代码之后）的主营业务简介 + 主营构成"""
    codes = [(c["code"], c["name"]) for c in ak.stock_info_a_code_name().to_dict("records") if c["code"] >= min_code]
    profiles, breakdowns = [], []
    for code, name in codes:
        df1 = ak.stock_zyjs_ths(code)
        profile = df1[["股票代码", "主营业务", "经营范围"]].rename(columns={"股票代码": "code", "主营业务": "business", "经营范围": "scope"})
        profile["update_time"] = datetime.now()
        profile["name"] = name
        profiles.append(profile)
        logger.info("fetched profile for {} {}", code, name)
        time.sleep(random.uniform(1, 2))

        zygc = stock_zygc_em(add_prefix(code, upper=True))
        if zygc.empty:
            logger.warning("no zygc for {} {}", code, name)
        else:
            breakdown = zygc.rename(columns=BREAKDOWN_RENAME)
            breakdown["name"] = name
            breakdowns.append(breakdown)
        time.sleep(random.uniform(1, 2))

    profile_df = pd.concat(profiles, ignore_index=True) if profiles else pd.DataFrame()
    breakdown_df = pd.concat(breakdowns, ignore_index=True) if breakdowns else pd.DataFrame()
    return profile_df, breakdown_df
