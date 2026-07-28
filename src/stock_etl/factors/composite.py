"""factors/composite.py — 技术面 + 财务面 + 估值面 综合打分"""
import numpy as np
import pandas as pd

HORIZON_WEIGHTS = {
    "short":  {"tech": 0.55, "fin": 0.30, "val": 0.15},
    "medium": {"tech": 0.40, "fin": 0.45, "val": 0.15},
    "long":   {"tech": 0.25, "fin": 0.55, "val": 0.20},
}


def calculate_valuation_score(pe, pb, peg) -> float:
    if pd.isna(pe) or pe <= 0:
        return 0.5
    score = 1.0 / (1 + np.log1p(pe)) + 1.0 / (1 + np.log1p(pb or 2))
    return float(np.clip(score / 2, 0, 1))


def calculate_composite_score(df: pd.DataFrame, horizon: str = "medium") -> pd.DataFrame:
    w = HORIZON_WEIGHTS.get(horizon, HORIZON_WEIGHTS["medium"])
    df = df.copy()
    df["total_composite_score"] = (
        df["total_technical_score"].fillna(0.5) * w["tech"]
        + df["total_financial_score"].fillna(0.5) * w["fin"]
        + df["valuation_score"].fillna(0.5) * w["val"]
    )
    df["composite_rank"] = df.groupby("date")["total_composite_score"].rank(ascending=False, method="min")
    return df


def build_composite_factor(technical_df: pd.DataFrame, financial_df: pd.DataFrame, horizon: str = "medium") -> pd.DataFrame:
    """合并技术因子（日频）与财务因子（季频），用 merge_asof 将每个交易日对齐到最近一期已公布财报"""
    technical_df = technical_df.copy().sort_values(["code", "date"])
    financial_df = financial_df.copy().sort_values(["code", "report_date"])

    # merge_asof 按 code 分组，对每个交易日找最近一期 report_date <= date 的财务数据
    merged = pd.merge_asof(
        technical_df,
        financial_df.rename(columns={"report_date": "date"}),
        on="date",
        by="code",
        direction="backward",
        suffixes=("_tech", "_fin"),
    )

    merged["valuation_score"] = merged.apply(
        lambda x: calculate_valuation_score(x.get("pe_ttm"), x.get("pb"), x.get("peg")), axis=1
    )
    return calculate_composite_score(merged, horizon=horizon)