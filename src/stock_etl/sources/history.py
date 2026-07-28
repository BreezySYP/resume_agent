"""sources/history.py — 股票列表 + 历史 K 线数据获取"""
import time
from random import randint

import akshare as ak
import baostock as bs
import pandas as pd
import requests
from loguru import logger
from shared.code_rule import add_prefix, remove_prefix


def _random_var(n: int = 13) -> str:
    return str(randint(10 ** (n - 1), 10 ** n - 1))

def get_all_codes() -> pd.DataFrame:
    return ak.stock_info_a_code_name()


def top_hs300(date: str | None = None) -> pd.DataFrame:
    date = date or time.strftime("%Y-%m-%d")
    bs.login()
    rs = bs.query_hs300_stocks(date=date)
    df = pd.DataFrame(rs.data, columns=["date", "code", "name"])
    df[["market", "code"]] = df["code"].str.split(".", expand=True)
    bs.logout()
    return df[["code", "name"]]


def fetch_history(name: str, code:str, start_date: str, end_date: str):
    code = add_prefix(code)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=&param={code},day,{start_date[:10]},{end_date},640,qfq"
    data_json = requests.get(url).json()
    symbol_node = data_json["data"][code]
    content = symbol_node.get("qfqday") or symbol_node["day"]
    df = pd.DataFrame([row[:6] for row in content], columns=["date", "open", "close", "high", "low", "volume"])
    df["code"] = remove_prefix(code)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("open", "close", "high", "low", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["name"] = name
    df["price_change"] = (df["close"] - df["close"].shift(1)).round(2)
    df[df.select_dtypes(include="float").columns] = df.select_dtypes(include="float").round(2)
    logger.info("✅ {} {} {} 条", code, name, len(df))
    return df

def fetch_all_history(start_date: str, end_date: str, min_code: str = "000000", on_batch=None, batch_size: int = 50) -> None:
    """全市场历史 K 线逐批抓取。
    每 batch_size 只股票处理完后调用 on_batch(df, last_code)：
    调用方负责在 on_batch 里先存 DB 再更新 checkpoint，保证数据不丢失。
    """
    from shared.code_rule import add_prefix

    codes = [(add_prefix(r["code"]), r["name"]) for r in get_all_codes().to_dict("records") if r["code"] >= min_code]
    logger.info("共 {} 支股票待拉取（min_code={}）", len(codes), min_code)

    frames = []
    last_code = None
    for code, name in codes:
        try:
            df = fetch_history(name, code, start_date, end_date)
            frames.append(df)
            last_code = code
        except Exception as e:
            logger.error("❌ {} {} 失败: {}", code, name, e)

        if on_batch and len(frames) >= batch_size and last_code:
            on_batch(pd.concat(frames, ignore_index=True), last_code)
            frames = []

        time.sleep(1)

    if on_batch and frames and last_code:
        on_batch(pd.concat(frames, ignore_index=True), last_code)


if __name__ == "__main__":
    print(fetch_history("klalaala", "000001", "2026-06-01", "2026-06-30"))