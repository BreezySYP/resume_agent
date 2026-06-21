"""sources/tick.py — 实时 tick 数据采集"""
import datetime
import random
import time

import akshare as ak
import pandas as pd
from loguru import logger
from shared.db.mysql import engine, get_connection
from shared.db.redis_cache import redis_cache_df_parquet

SINA_MAX_PAGE = 56
BATCH_INTERVAL = 2


def now_date() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def get_job_by_date(date_str: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tick_job WHERE date = %s", (date_str,))
            return cursor.fetchone()


def today_job():
    today = now_date()
    result = get_job_by_date(today)
    if result is None or str(result[1]) != today:
        pd.DataFrame([{"date": today}]).to_sql("tick_job", con=engine, if_exists="append", index=False)
        result = get_job_by_date(today)
    return result


@redis_cache_df_parquet(expire_seconds=172800)
def sina_realtime(current_page: int = 1, item_per_page: int = 100) -> pd.DataFrame:
    logger.debug("Fetching Sina realtime page {}", current_page)
    url = (
        f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"Market_Center.getHQNodeData?page={current_page}&num={item_per_page}"
        f"&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=init"
    )
    return pd.read_json(url)


def get_tx_ticks(code: str) -> pd.DataFrame:
    try:
        df = ak.stock_zh_a_tick_tx_js(code)
        if df.empty:
            return pd.DataFrame()
        df.columns = ["ticktime", "trade", "pricechange", "volume", "amount", "logic_check"]
        df["logic_check"] = df["logic_check"].map({"卖盘": "-1", "买盘": "1", "中性盘": "0"})
        return df
    except Exception as e:
        logger.error("get_tx_ticks {} error: {}", code, e)
        return pd.DataFrame()


def load_all_ticks_today() -> None:
    job = today_job()
    job_id = job[0]
    logger.info("Job ID: {}", job_id)
    pages = list(range(SINA_MAX_PAGE))
    random.shuffle(pages)
    for page in pages:
        stocks = sina_realtime(page)
        stocks = stocks[~stocks["symbol"].str.startswith("bj")]
        if stocks.empty:
            time.sleep(BATCH_INTERVAL + 1)
            continue
        for _, row in stocks.iterrows():
            ticks = get_tx_ticks(row["symbol"])
            if ticks.empty:
                time.sleep(BATCH_INTERVAL)
                continue
            ticks["symbol"] = row["symbol"]
            ticks["name"] = row["name"]
            ticks["code"] = row["code"]
            ticks["settlement"] = row["settlement"]
            ticks["job_id"] = job_id
            try:
                ticks.to_sql("tick_price", con=engine, if_exists="append", index=False)
                logger.info("✅ {} {} {} 条", row["symbol"], row["name"], len(ticks))
            except Exception as e:
                logger.error("❌ insert {} error: {}", row["symbol"], e)
