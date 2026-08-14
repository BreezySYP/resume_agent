"""factors.financial_factor 财务因子打分测试。"""
import pandas as pd
from factors.financial_factor import OUTPUT_COLS, build_financial_factor


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "code": ["A", "B", "A", "B"],
        "name": ["a", "b", "a", "b"],
        "report_date": pd.to_datetime(["2025-06-30", "2025-06-30", "2025-12-31", "2025-12-31"]),
        "roe": [0.10, 0.20, 0.15, 0.05],
        "roa": [0.05, 0.10, 0.08, 0.02],
        "net_margin": [0.10, 0.20, 0.12, 0.08],
        "revenue_growth": [10.0, 20.0, 15.0, 5.0],
        "profit_growth": [10.0, 30.0, 20.0, 8.0],
        "operating_cashflow": [5.0, 10.0, 8.0, 2.0],
        "net_profit": [10.0, 10.0, 10.0, 10.0],
        "asset_liability_ratio": [0.5, 0.6, 0.4, 0.8],
    })


def test_output_columns_and_shape():
    out = build_financial_factor(_sample_df())
    assert set(OUTPUT_COLS) <= set(out.columns)
    assert len(out) == 4


def test_rank_by_report_date():
    out = build_financial_factor(_sample_df())
    assert sorted(out["total_financial_rank"].unique()) == [1, 2]
    assert out.groupby("report_date")["total_financial_rank"].min().min() == 1


def test_better_roe_scores_higher_within_date():
    out = build_financial_factor(_sample_df())
    b = out[(out["code"] == "B") & (out["report_date"] == "2025-06-30")].iloc[0]
    assert b["profitability_score"] == 1.0
    assert b["quality_score"] == 1.0  # fcf_ratio B=1.0 > A=0.5


def test_safety_score_prefers_lower_leverage():
    out = build_financial_factor(_sample_df())
    a = out[(out["code"] == "A") & (out["report_date"] == "2025-06-30")].iloc[0]
    b = out[(out["code"] == "B") & (out["report_date"] == "2025-06-30")].iloc[0]
    assert a["safety_score"] > b["safety_score"]
