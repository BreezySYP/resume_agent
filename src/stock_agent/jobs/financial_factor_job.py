from core.db import engine
import pandas as pd
import numpy as np


def load_data():
    sql = """
    SELECT *
    FROM financial_feature
    """
    df = pd.read_sql(sql, engine)
    
    # 确保日期格式正确并排序
    df['date'] = pd.to_datetime(df['report_date'])
    # df = df.sort_values(["code", "report_date"]).reset_index(drop=True)
    
    return df

def build_factor(df):

    df = df.copy()

    # ========= Profitability =========

    roe_rank = (
        df.groupby("date")["roe"]
          .rank(pct=True)
    )

    roa_rank = (
        df.groupby("date")["roa"]
          .rank(pct=True)
    )

    margin_rank = (
        df.groupby("date")["net_margin"]
          .rank(pct=True)
    )

    df["profitability_score"] = (
        roe_rank * 0.5 +
        roa_rank * 0.2 +
        margin_rank * 0.3
    )

    # ========= Growth =========

    revenue_rank = (
        df.groupby("date")["revenue_growth"]
          .rank(pct=True)
    )

    profit_rank = (
        df.groupby("date")["profit_growth"]
          .rank(pct=True)
    )

    df["growth_score"] = (
        revenue_rank * 0.4 +
        profit_rank * 0.6
    )

    # ========= Quality =========

    df["fcf_ratio"] = (
        df["operating_cashflow"] /
        df["net_profit"]
    )

    df["quality_score"] = (
        df.groupby("date")["fcf_ratio"]
          .rank(pct=True)
    )

    # ========= Safety =========

    liability_rank = (
        df.groupby("date")["asset_liability_ratio"]
          .rank(pct=True)
    )

    df["safety_score"] = (
        1 - liability_rank
    )

    # ========= Total =========

    df["total_financial_score"] = (
        df["profitability_score"] * 0.35 +
        df["growth_score"] * 0.35 +
        df["quality_score"] * 0.15 +
        df["safety_score"] * 0.15
    )

    # ========= Final Rank =========

    df["total_financial_rank"] = (
        df.groupby("report_date")["total_financial_score"]
          .rank(ascending=False, method="min")
    )

    return df[["code", "name", "report_date", "profitability_score", "growth_score", "quality_score", "safety_score", "total_financial_score", "total_financial_rank"]]

if __name__ == "__main__":
    df = load_data()
    df = build_factor(df)
    df.to_sql(
        "financial_factor",
        engine,
        if_exists="replace",   # 或者用 'append' 如果是增量更新
        index=False,
        chunksize=1000,
        method='multi'
    )
    print(f"✅ 已成功保存 {len(df)} 条记录到 financial_factor 表")