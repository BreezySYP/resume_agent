"""data/tusharewrapper.py — 历史 K 线数据获取"""
import json, re, time
from urllib.request import urlopen
from random import randint
import pandas as pd
import requests
from requests import Request
from tushare.stock import cons as ct
from tushare.util import dateu as du
from data.coderule import remove_prefix
import tushare as ts


def _random(n=13):
    return str(randint(10 ** (n - 1), 10 ** n - 1))


def get_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    symbol: sh600519
    start/end: 1988-01-01
    """
    url = (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?_var=&param={symbol},day,{start},{end},640,qfq"
    )
    data_json = requests.get(url).json()
    symbol_node = data_json["data"][symbol]
    content     = symbol_node.get("qfqday") or symbol_node["day"]
    df = pd.DataFrame([row[:6] for row in content],
                      columns=["date", "open", "close", "high", "low", "volume"])
    df["code"]   = remove_prefix(symbol)
    df["date"]   = pd.to_datetime(df["date"],   errors="coerce")
    df["open"]   = pd.to_numeric(df["open"],   errors="coerce")
    df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
    df["high"]   = pd.to_numeric(df["high"],   errors="coerce")
    df["low"]    = pd.to_numeric(df["low"],    errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df

# print(ts.get_stock_basics())