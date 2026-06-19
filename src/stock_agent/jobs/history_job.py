"""jobs/history_job.py — 沪深300历史 K 线数据入库"""
import time, datetime
import baostock as bs
import pandas as pd
from loguru import logger
from core.db import engine
from data.coderule import add_prefix
from data import tusharewrapper as ts
import akshare as ak


def now_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def top_hs300(date: str = now_str()) -> pd.DataFrame:
    bs.login()
    rs = bs.query_hs300_stocks(date=date)
    df = pd.DataFrame(rs.data, columns=["date", "code", "name"])
    df[["market", "code"]] = df["code"].str.split(".", expand=True)
    bs.logout()
    return df[["code", "name"]]

def get_codes():
    return ak.stock_info_a_code_name()

def save_history(startdate: str = "2025-01-01", enddate: str = "2050-01-01"):
    codes = [(add_prefix(r["code"]), r["name"]) for r in get_codes().to_dict("records")]
    logger.info("共 {} 支股票待入库", len(codes))
    for code, name in codes:
        try:
            df = ts.get_history(code, startdate, enddate)
            df["name"]         = name
            df["price_change"] = (df["close"] - df["close"].shift(1)).round(2)
            float_cols = df.select_dtypes(include="float").columns
            df[float_cols] = df[float_cols].round(2)
            df.to_sql("history", con=engine, if_exists="append", index=False)
            logger.info("✅ {} {} {} 条", code, name, len(df))
        except Exception as e:
            logger.error("❌ {} {} 失败: {}", code, name, e)
        time.sleep(1)


if __name__ == "__main__":
    # save_history()
    # bs.login()
    # rs = bs.query_all_stock()
    # print(rs)
    # codes = ak.stock_info_a_code_name()
    # print(codes['code'].to_list())

    help(ak)
    print(ak.__version__)
    ak.stock_financial_abstract(symbol="000001")