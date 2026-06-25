"""sources/profile.py — 个股主营业务简介 + 主营构成抓取"""
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


def fetch_profiles_and_breakdowns(min_code: str = "000000", on_batch=None, batch_size: int = 50) -> None:
    """逐批抓取主营业务简介 + 主营构成。每 batch_size 只股票后调用 on_batch(profile_df, breakdown_df, last_code)：
    调用方负责在 on_batch 里先存 DB 再更新 checkpoint。
    """
    codes = [(c["code"], c["name"]) for c in ak.stock_info_a_code_name().to_dict("records") if c["code"] >= min_code]

    profile_frames, breakdown_frames = [], []
    last_code = None
    for code, name in codes:
        df1 = ak.stock_zyjs_ths(code)
        p = df1[["股票代码", "主营业务", "经营范围"]].rename(columns={"股票代码": "code", "主营业务": "business", "经营范围": "scope"})
        p["update_time"] = datetime.now()
        p["name"] = name
        profile_frames.append(p)
        logger.info("fetched profile for {} {}", code, name)
        time.sleep(random.uniform(1, 2))

        zygc = stock_zygc_em(add_prefix(code, upper=True))
        if zygc.empty:
            logger.warning("no zygc for {} {}", code, name)
        else:
            b = zygc.rename(columns=BREAKDOWN_RENAME)
            b["name"] = name
            breakdown_frames.append(b)

        last_code = code

        if on_batch and len(profile_frames) >= batch_size and last_code:
            on_batch(
                pd.concat(profile_frames, ignore_index=True),
                pd.concat(breakdown_frames, ignore_index=True) if breakdown_frames else pd.DataFrame(),
                last_code,
            )
            profile_frames, breakdown_frames = [], []

        time.sleep(random.uniform(1, 2))

    if on_batch and profile_frames and last_code:
        on_batch(
            pd.concat(profile_frames, ignore_index=True),
            pd.concat(breakdown_frames, ignore_index=True) if breakdown_frames else pd.DataFrame(),
            last_code,
        )

# if __name__ == "__main__":
#     # fetch_profiles_and_breakdowns()