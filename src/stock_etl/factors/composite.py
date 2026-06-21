"""factors/composite.py — 技术面 + 财务面 + 估值面 综合打分"""
import numpy as np
import pandas as pd

HORIZON_WEIGHTS = {
    "short": {"tech": 0.55, "fin": 0.30, "val": 0.15},
    "medium": {"tech": 0.40, "fin": 0.45, "val": 0.15},
    "long": {"tech": 0.25, "fin": 0.55, "val": 0.20},
}


def calculate_valuation_score(pe, pb, peg) -> float:
    """估值打分（越低越好），缺失或非正 PE 给中性分"""
    if pd.isna(pe) or pe <= 0:
        return 0.5
    score = 1.0 / (1 + np.log1p(pe)) + 1.0 / (1 + np.log1p(pb or 2))
    return float(np.clip(score / 2, 0, 1))


def calculate_composite_score(df: pd.DataFrame, horizon: str = "medium") -> pd.DataFrame:
    """按 horizon 动态加权合并技术面/财务面/估值面分数"""
    w = HORIZON_WEIGHTS.get(horizon, HORIZON_WEIGHTS["medium"])
    df = df.copy()
    df["total_composite_score"] = (
        df["total_technical_score"].fillna(0.5) * w["tech"]
        + df["total_financial_score"].fillna(0.5) * w["fin"]
        + df["valuation_score"].fillna(0.5) * w["val"]
    )
    df["composite_rank"] = df.groupby("date")["total_composite_score"].rank(ascending=False, method="min")
    return df


def build_composite_factor(technical_df: pd.DataFrame, financial_df: pd.DataFrame, price_valuation_df: pd.DataFrame, horizon: str = "medium") -> pd.DataFrame:
    """合并技术因子、财务因子、估值数据，计算综合评分"""
    df = technical_df.merge(financial_df, on=["code", "date"], how="inner", suffixes=("_tech", "_fin"))
    df = df.merge(price_valuation_df, on=["code", "date"], how="left")
    df["valuation_score"] = df.apply(lambda x: calculate_valuation_score(x["pe_ttm"], x["pb"], x["peg"]), axis=1)
    return calculate_composite_score(df, horizon=horizon)
