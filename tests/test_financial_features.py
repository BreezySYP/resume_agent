"""factors.financial_feature 财务特征工程测试。"""
import numpy as np
import pandas as pd
from factors.financial_feature import build_financial_features


def _quarterly_df(code: str) -> pd.DataFrame:
    dates = pd.to_datetime([
        "2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
        "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
    ])
    return pd.DataFrame({
        "code": [code] * 8,
        "name": [code] * 8,
        "report_date": dates,
        "revenue": [100.0, 110.0, 120.0, 130.0, 200.0, 210.0, 220.0, 230.0],
        "net_profit": [10.0, 11.0, 12.0, 13.0, 20.0, 21.0, 22.0, 23.0],
        "operating_cashflow": [5.0, 5.0, 5.0, 5.0, 10.0, 10.0, 10.0, 10.0],
        "roe": [0.1] * 8,
        "net_margin": [0.2] * 8,
    })


def test_yoy_growth_shift_4_quarters():
    df = build_financial_features(_quarterly_df("A"))
    a = df[df["code"] == "A"].reset_index(drop=True)
    assert a.loc[4, "revenue_growth"] == 100.0
    assert a.loc[4, "profit_growth"] == 100.0
    assert np.isnan(a.loc[0, "revenue_growth"])


def test_qoq_growth():
    df = build_financial_features(_quarterly_df("A"))
    a = df[df["code"] == "A"].reset_index(drop=True)
    assert a.loc[1, "revenue_growth_qoq"] == 10.0
    assert np.isnan(a.loc[0, "revenue_growth_qoq"])


def test_fcf_ratio_and_quality_score():
    df = build_financial_features(_quarterly_df("A"))
    a = df[df["code"] == "A"].reset_index(drop=True)
    assert a.loc[0, "fcf_ratio"] == 0.5
    expected_quality = 0.1 * 0.4 + 0.2 * 0.3 + 0.5 * 0.3
    assert np.isclose(a.loc[0, "quality_score"], expected_quality)


def test_multiple_codes_isolated():
    combined = pd.concat([_quarterly_df("A"), _quarterly_df("B")], ignore_index=True)
    df = build_financial_features(combined)
    assert len(df) == 16
    assert df.groupby("code")["revenue_growth"].apply(lambda s: s.iloc[4]).to_dict() == {"A": 100.0, "B": 100.0}


def test_zero_profit_fcf_ratio_becomes_nan():
    df = _quarterly_df("A")
    df.loc[0, "net_profit"] = 0.0
    out = build_financial_features(df)
    assert np.isnan(out.loc[0, "fcf_ratio"])
