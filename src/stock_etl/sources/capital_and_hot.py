"""sources/capital_and_hot.py — 热门板块 + 个股主力资金流抓取（东方财富接口）"""
from datetime import datetime

import pandas as pd
import requests
from loguru import logger

HEADERS = {"User-Agent": "Mozilla/5.0"}

HOT_SECTOR_RENAME = {
    "f12": "sector_code", "f14": "sector_name", "f3": "change_pct", "f2": "index_value",
    "f8": "turnover_rate", "f62": "net_inflow", "f128": "leading_stock_name", "f140": "leading_stock_code",
}
HOT_SECTOR_COLS = [
    "date", "sector_code", "sector_name", "sector_type", "change_pct", "index_value", "turnover_rate",
    "net_inflow", "leading_stock_name", "leading_stock_code", "attention_score", "fetch_time",
]
CAPITAL_FLOW_RENAME = {"f12": "code", "f14": "name", "f62": "main_net_inflow", "f184": "large_net_inflow", "f3": "change_pct"}
CAPITAL_FLOW_COLS = ["code", "date", "main_net_inflow", "large_net_inflow", "change_pct"]


def fetch_hot_sectors(pz: int = 300) -> pd.DataFrame | None:
    logger.info("正在获取热门概念板块...")
    params = {
        "pn": "1", "pz": pz, "po": "1", "np": "1", "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": "f3", "fs": "m:90 t:3 f:!50",
        "fields": "f2,f3,f4,f8,f12,f14,f15,f16,f17,f18,f20,f21,f24,f25,f22,f33,f11,f62,f128,f124,f107,f104,f105,f136",
    }
    try:
        resp = requests.get("https://79.push2.eastmoney.com/api/qt/clist/get", params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        df = pd.DataFrame(resp.json()["data"]["diff"]).rename(columns=HOT_SECTOR_RENAME)
        df["date"] = datetime.now().date()
        df["sector_type"] = "concept"
        df["fetch_time"] = datetime.now()
        df["attention_score"] = df["change_pct"].rank(pct=True)
        return df[HOT_SECTOR_COLS]
    except Exception as e:
        logger.error("❌ 热门板块获取失败: {}", e)
        return None


def fetch_capital_flow(pz: int = 100) -> pd.DataFrame | None:
    logger.info("正在获取个股主力资金流排名...")
    params = {
        "pn": "1", "pz": pz, "po": "1", "np": "1", "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": "f62", "fs": "m:0 t:6 f:!2",
        "fields": "f12,f14,f2,f3,f62,f184,f183,f105,f162,f109,f175,f177",
    }
    try:
        resp = requests.get("https://push2.eastmoney.com/api/qt/clist/get", params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        df = pd.DataFrame(resp.json()["data"]["diff"]).rename(columns=CAPITAL_FLOW_RENAME)
        df["date"] = datetime.now().date()
        df["code"] = df["code"].str.zfill(6)
        return df[CAPITAL_FLOW_COLS]
    except Exception as e:
        logger.error("❌ 资金流获取失败: {}", e)
        return None
    

if __name__ == "__main__":
    print(fetch_hot_sectors())
    print(fetch_capital_flow()
          
          
          
          
          
          )
