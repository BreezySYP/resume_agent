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
    """
    构建技术指标
    关键：先按日期排序！
    """
    # ✅ 1. 确保按时间升序排列
    g = g.sort_values("date").reset_index(drop=True)
    
    # 复制避免修改原数据
    g = g.copy()
    
    # 计算技术指标
    g["ma20_ratio"] = g["close"] / g["close"].rolling(20, min_periods=1).mean()
    g["ma60_ratio"] = g["close"] / g["close"].rolling(60, min_periods=1).mean()
    g["ma120_ratio"] = g["close"] / g["close"].rolling(120, min_periods=1).mean()
    g["rsi14"] = rsi(g["close"], 14)
    g["mom20"] = momentum(g["close"], 20)
    g["macd_hist"] = macd_hist(g["close"])
    g["obv"] = obv(g["close"], g["volume"])
    g["mfi14"] = mfi(g["high"], g["low"], g["close"], g["volume"], 14)
    
    return g

def build_technical_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    输入: code/name/date/open/high/low/close/volume 历史行情
    输出: 截面排名后的技术因子
    """
    # ✅ 2. 整体先按 code 和 date 排序，提高效率
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    
    # ✅ 3. 使用 groupby.apply 替代循环，更高效
    df = df.groupby("code", group_keys=False).apply(_build_indicators)
    
    # ✅ 4. 处理 NaN：用前向填充或中位数填充
    for col in RANK_COLS:
        # 对每个股票，用前向填充处理 NaN
        df[col] = df.groupby("code")[col].ffill()
        # 如果还有 NaN，用中位数填充
        df[col] = df.groupby("code")[col].transform(lambda x: x.fillna(x.median()))
    
    # ✅ 5. 计算截面排名（日期为截面）
    for col in RANK_COLS:
        df[col + "_rank"] = df.groupby("date")[col].rank(pct=True)
    
    # 计算复合得分
    df["trend_score"] = (
        df["ma20_ratio_rank"] * 0.3 + 
        df["ma60_ratio_rank"] * 0.3 + 
        df["ma120_ratio_rank"] * 0.4
    )
    
    df["momentum_score"] = (
        df["rsi14_rank"] * 0.3 + 
        df["mom20_rank"] * 0.4 + 
        df["macd_hist_rank"] * 0.3
    )
    
    df["volume_score"] = (
        df["obv_rank"] * 0.5 + 
        df["mfi14_rank"] * 0.5
    )
    
    df["total_technical_score"] = (
        df["trend_score"] * 0.4 + 
        df["momentum_score"] * 0.4 + 
        df["volume_score"] * 0.2
    )
    
    # ✅ 6. 按日期计算技术排名（1为最强）
    df["technical_rank"] = df.groupby("date")["total_technical_score"].rank(
        ascending=False,  # 分数越高排名越靠前
        method="min"
    )
    
    return df[OUTPUT_COLS]