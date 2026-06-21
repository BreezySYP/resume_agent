"""research/common.py — 技术因子回测/诊断共用的数据加载与预处理"""
import numpy as np
import pandas as pd
from data_loader import load_df


def load_technical_and_price() -> tuple[pd.DataFrame, pd.DataFrame]:
    factor_df = load_df("SELECT code, date, total_technical_score FROM technical_factor", "technical_factor")
    price_df = load_df("SELECT code, date, close FROM history", "history")
    factor_df["date"] = pd.to_datetime(factor_df["date"])
    price_df["date"] = pd.to_datetime(price_df["date"])
    return factor_df, price_df


def prepare_future_return(factor_df: pd.DataFrame, price_df: pd.DataFrame, hold_days: int = 20) -> pd.DataFrame:
    """计算未来 N 日收益并与因子合并，过滤掉缺失值"""
    price_df = price_df.sort_values(["code", "date"]).copy()
    price_df["future_close"] = price_df.groupby("code")["close"].shift(-hold_days)
    price_df["future_return"] = price_df["future_close"] / price_df["close"] - 1

    merged = factor_df.merge(price_df[["code", "date", "close", "future_return"]], on=["code", "date"], how="inner")
    return merged.dropna(subset=["total_technical_score", "future_return"])


def add_regime(df: pd.DataFrame, q: float = 0.8) -> pd.DataFrame:
    """按分位数划分 normal / extreme 两种因子区间，用于双策略回测"""
    df = df.copy()
    threshold = df["total_technical_score"].quantile(q)
    df["regime"] = np.where(df["total_technical_score"] >= threshold, "extreme", "normal")
    return df
