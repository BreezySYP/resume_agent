"""factors/technical.py — 技术面因子计算（趋势/动量/量能）"""
import numpy as np
import pandas as pd


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(window).mean() / loss.rolling(window).mean()
    return 100 - (100 / (1 + rs))


def momentum(close: pd.Series, window: int) -> pd.Series:
    return close / close.shift(window) - 1


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 14) -> pd.Series:
    tp = (high + low + close) / 3
    mf = tp * volume
    pos_sum = mf.where(tp.diff() > 0, 0).rolling(window).sum()
    neg_sum = mf.where(tp.diff() < 0, 0).rolling(window).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - 100 / (1 + mfr)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd_hist(close: pd.Series) -> pd.Series:
    macd_line = ema(close, 12) - ema(close, 26)
    signal = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - signal


RANK_COLS = ["ma20_ratio", "ma60_ratio", "ma120_ratio", "rsi14", "mom20", "macd_hist", "obv", "mfi14"]
OUTPUT_COLS = ["code", "name", "date", "trend_score", "momentum_score", "volume_score", "total_technical_score", "technical_rank"]


def _build_indicators(g: pd.DataFrame) -> pd.DataFrame:
    g = g.copy()
    g["ma20_ratio"] = g["close"] / g["close"].rolling(20).mean()
    g["ma60_ratio"] = g["close"] / g["close"].rolling(60).mean()
    g["ma120_ratio"] = g["close"] / g["close"].rolling(120).mean()
    g["rsi14"] = rsi(g["close"], 14)
    g["mom20"] = momentum(g["close"], 20)
    g["macd_hist"] = macd_hist(g["close"])
    g["obv"] = obv(g["close"], g["volume"])
    g["mfi14"] = mfi(g["high"], g["low"], g["close"], g["volume"], 14)
    return g


def build_technical_factor(df: pd.DataFrame) -> pd.DataFrame:
    """输入: code/name/date/open/high/low/close/volume 历史行情，输出: 截面排名后的技术因子"""
    df = pd.concat([_build_indicators(g) for _, g in df.groupby("code")])

    for col in RANK_COLS:
        df[col + "_rank"] = df.groupby("date")[col].rank(pct=True)

    df["trend_score"] = df["ma20_ratio_rank"] * 0.3 + df["ma60_ratio_rank"] * 0.3 + df["ma120_ratio_rank"] * 0.4
    df["momentum_score"] = df["rsi14_rank"] * 0.3 + df["mom20_rank"] * 0.4 + df["macd_hist_rank"] * 0.3
    df["volume_score"] = df["obv_rank"] * 0.5 + df["mfi14_rank"] * 0.5
    df["total_technical_score"] = df["trend_score"] * 0.4 + df["momentum_score"] * 0.4 + df["volume_score"] * 0.2
    df["technical_rank"] = df.groupby("date")["total_technical_score"].rank(ascending=False, method="min")

    return df[OUTPUT_COLS]
