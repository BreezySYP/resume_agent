"""trading_calendar.next_trading_day 测试（注入交易日，不依赖 akshare）。"""
import pandas as pd
from trading_calendar import next_trading_day


def test_next_trading_day_normal():
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    assert next_trading_day("2026-01-01", trade_dates=dates) == "2026-01-02"


def test_skips_non_trading_days():
    # 01-02(五) 的下一个交易日是 01-05(一)
    dates = pd.to_datetime(["2026-01-02", "2026-01-05"])
    assert next_trading_day("2026-01-01", trade_dates=dates) == "2026-01-02"


def test_no_later_date_falls_back_to_next_weekday():
    dates = pd.to_datetime(["2025-12-30"])
    # 2026-01-02 是周五，无更晚交易日 → 退化为下周一 01-05
    assert next_trading_day("2026-01-02", trade_dates=dates) == "2026-01-05"


def test_empty_calendar_falls_back():
    empty = pd.Series([], dtype="datetime64[ns]")
    assert next_trading_day("2026-01-02", trade_dates=empty) == "2026-01-05"


def test_bad_calendar_type_falls_back():
    bad = pd.Series(["2026-01-01"])  # 非 datetime 类型 → 比较抛异常 → 退化
    assert next_trading_day("2026-01-01", trade_dates=bad) == "2026-01-02"
