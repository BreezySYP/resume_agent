"""factors.technical 技术指标与因子构建测试。"""
import numpy as np
import pandas as pd
from factors.technical import (
    OUTPUT_COLS,
    build_technical_factor,
    ema,
    macd_hist,
    mfi,
    momentum,
    obv,
    rsi,
)


def test_momentum():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = momentum(close, window=2)
    assert np.isnan(result.iloc[0]) and np.isnan(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[3] == 1.0
    assert np.isclose(result.iloc[4], 2.0 / 3.0)


def test_obv_direction():
    close = pd.Series([1.0, 2.0, 1.0, 3.0])
    volume = pd.Series([10.0, 10.0, 10.0, 10.0])
    result = obv(close, volume)
    assert result.tolist() == [0.0, 10.0, 0.0, 10.0]


def test_rsi_up_only_trend_is_100():
    close = pd.Series(np.arange(1, 30, dtype=float))
    result = rsi(close, window=14)
    assert np.isclose(result.iloc[-1], 100.0)


def test_mfi_needs_negative_flow():
    close = pd.Series(np.arange(1, 20, dtype=float))
    high = close * 1.01
    low = close * 0.99
    volume = pd.Series([100.0] * 19)
    result = mfi(high, low, close, volume, window=14)
    assert len(result) == 19
    assert np.isnan(result.iloc[-1])  # 全部上涨 → 无负资金流 → NaN


def test_ema_and_macd_hist():
    close = pd.Series(np.arange(1, 60, dtype=float))
    e = ema(close, span=3)
    assert not np.isnan(e.iloc[-1])
    assert 1 < e.iloc[-1] < 59
    hist = macd_hist(close)
    assert not np.isnan(hist.iloc[-1])


def test_build_technical_factor_end_to_end():
    dates = pd.date_range("2025-01-01", periods=130, freq="B")
    rows = []
    for code, base in (("600519", 100.0), ("000001", 10.0)):
        for i, d in enumerate(dates):
            # 带波动的价格，保证 mfi/rsi 有涨有跌可计算
            close = base + i * 0.3 + 5.0 * np.sin(i / 7.0)
            rows.append({
                "code": code,
                "name": code,
                "date": d,
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.98,
                "close": close,
                "volume": 1000.0 + i,
            })
    df = pd.DataFrame(rows)

    out = build_technical_factor(df)

    assert set(OUTPUT_COLS) <= set(out.columns)
    assert len(out) == len(df)
    assert out["total_technical_score"].between(0, 1).all()
    assert out.groupby("date")["technical_rank"].min().min() == 1
    assert out.groupby("date")["technical_rank"].max().max() == 2
