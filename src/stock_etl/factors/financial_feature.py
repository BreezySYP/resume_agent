"""factors/financial_feature.py — 财务原始指标 -> 特征工程（成长性/现金流质量/杠杆）"""
import numpy as np
import pandas as pd


def build_financial_features(df: pd.DataFrame) -> pd.DataFrame:
    """输入: financial_statement 长表，输出: 带成长率/质量分的特征表"""
    df = df.copy()
    df = df.sort_values(["code", "report_date"]).reset_index(drop=True)

    for col, growth_col in (("revenue", "revenue_growth"), ("net_profit", "profit_growth")):
        prev = df.groupby("code")[col].shift(4)
        df[growth_col] = ((df[col] - prev) / prev * 100).round(4)

    df["revenue_growth_qoq"] = (df.groupby("code")["revenue"].pct_change() * 100).round(4)
    df["profit_growth_qoq"] = (df.groupby("code")["net_profit"].pct_change() * 100).round(4)

    df["fcf_ratio"] = df["operating_cashflow"] / df["net_profit"]
    if "asset_liability_ratio" in df.columns:
        df["leverage_score"] = 1 / (1 + df["asset_liability_ratio"])

    df["quality_score"] = df.get("roe", 0) * 0.4 + df.get("net_margin", 0) * 0.3 + df["fcf_ratio"].fillna(0) * 0.3
    df = df.replace([np.inf, -np.inf], np.nan)
    return df
