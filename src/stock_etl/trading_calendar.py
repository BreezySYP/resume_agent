"""trading_calendar.py — A 股交易日历，用于断点续跑时把 '上次完成日期' 推进到下一个交易日"""
import datetime
from functools import lru_cache

import akshare as ak
import pandas as pd
from loguru import logger


@lru_cache(maxsize=1)
def _trade_dates() -> pd.Series:
    """全部 A 股交易日（缓存一次进程内复用）"""
    df = ak.tool_trade_date_hist_sina()
    return pd.to_datetime(df["trade_date"]).sort_values().reset_index(drop=True)


def next_trading_day(date_str: str) -> str:
    """返回严格晚于 date_str 的下一个交易日；取不到交易日历时退化为自然日+1（跳过周末）"""
    date = pd.to_datetime(date_str)
    try:
        dates = _trade_dates()
        later = dates[dates > date]
        if not later.empty:
            return later.iloc[0].strftime("%Y-%m-%d")
        logger.warning("交易日历中没有晚于 {} 的日期，退化为自然日+1", date_str)
    except Exception as e:
        logger.warning("获取交易日历失败: {}，退化为自然日+1", e)

    next_date = date + datetime.timedelta(days=1)
    while next_date.weekday() >= 5:  # 5=Sat, 6=Sun
        next_date += datetime.timedelta(days=1)
    return next_date.strftime("%Y-%m-%d")