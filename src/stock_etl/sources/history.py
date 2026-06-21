"""sources/history.py — 股票列表 + 历史 K 线数据获取"""
import time
from random import randint

import akshare as ak
import baostock as bs
import pandas as pd
import requests
from loguru import logger
from shared.code_rule import remove_prefix


def _random_var(n: int = 13) -> str:
    return str(randint(10 ** (n - 1), 10 ** n - 1))


def get_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    """symbol: sh600519, start/end: 1988-01-01"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=&param={symbol},day,{start},{end},640,qfq"
    data_json = requests.get(url).json()
    symbol_node = data_json["data"][symbol]
    content = symbol_node.get("qfqday") or symbol_node["day"]
    df = pd.DataFrame([row[:6] for row in content], columns=["date", "open", "close", "high", "low", "volume"])
    df["code"] = remove_prefix(symbol)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("open", "close", "high", "low", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_all_codes() -> pd.DataFrame:
    """全市场股票代码 + 名称"""
    return ak.stock_info_a_code_name()


def top_hs300(date: str | None = None) -> pd.DataFrame:
    """沪深300成分股"""
    date = date or time.strftime("%Y-%m-%d")
    bs.login()
    rs = bs.query_hs300_stocks(date=date)
    df = pd.DataFrame(rs.data, columns=["date", "code", "name"])
    df[["market", "code"]] = df["code"].str.split(".", expand=True)
    bs.logout()
    return df[["code", "name"]]


def fetch_all_history(start_date: str = "2025-01-01", end_date: str = "2050-01-01") -> pd.DataFrame:
    """全市场历史 K 线（逐只股票请求，附带限流）"""
    from shared.code_rule import add_prefix

    codes = [(add_prefix(r["code"]), r["name"]) for r in get_all_codes().to_dict("records")]
    logger.info("共 {} 支股票待拉取", len(codes))
    frames = []
    for code, name in codes:
        try:
            df = get_history(code, start_date, end_date)
            df["name"] = name
            df["price_change"] = (df["close"] - df["close"].shift(1)).round(2)
            float_cols = df.select_dtypes(include="float").columns
            df[float_cols] = df[float_cols].round(2)
            frames.append(df)
            logger.info("✅ {} {} {} 条", code, name, len(df))
        except Exception as e:
            logger.error("❌ {} {} 失败: {}", code, name, e)
        time.sleep(1)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
