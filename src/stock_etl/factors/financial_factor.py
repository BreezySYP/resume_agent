"""factors/financial_factor.py — 财务因子打分（盈利能力/成长/质量/安全）"""
import pandas as pd

OUTPUT_COLS = ["code", "name", "report_date", "profitability_score", "growth_score", "quality_score", "safety_score", "total_financial_score", "total_financial_rank"]


def build_financial_factor(df: pd.DataFrame) -> pd.DataFrame:
    """输入: financial_feature 特征表，输出: 截面排名后的财务因子"""
    df = df.copy()

    profitability = df.groupby("date")["roe"].rank(pct=True) * 0.5 + df.groupby("date")["roa"].rank(pct=True) * 0.2 + df.groupby("date")["net_margin"].rank(pct=True) * 0.3
    df["profitability_score"] = profitability

    growth = df.groupby("date")["revenue_growth"].rank(pct=True) * 0.4 + df.groupby("date")["profit_growth"].rank(pct=True) * 0.6
    df["growth_score"] = growth

    df["fcf_ratio"] = df["operating_cashflow"] / df["net_profit"]
    df["quality_score"] = df.groupby("date")["fcf_ratio"].rank(pct=True)

    df["safety_score"] = 1 - df.groupby("date")["asset_liability_ratio"].rank(pct=True)

    df["total_financial_score"] = (
        df["profitability_score"] * 0.35 + df["growth_score"] * 0.35 + df["quality_score"] * 0.15 + df["safety_score"] * 0.15
    )
    df["total_financial_rank"] = df.groupby("report_date")["total_financial_score"].rank(ascending=False, method="min")

    return df[OUTPUT_COLS]
