"""factors.composite 综合打分与 merge_asof 测试。"""
import math

import numpy as np
import pandas as pd
from factors.composite import (
    HORIZON_WEIGHTS,
    build_composite_factor,
    calculate_composite_score,
    calculate_valuation_score,
)


def test_valuation_score_missing_or_non_positive():
    assert calculate_valuation_score(float("nan"), 2, 1) == 0.5
    assert calculate_valuation_score(0, 2, 1) == 0.5
    assert calculate_valuation_score(-5, 2, 1) == 0.5


def test_valuation_score_nan_pb_does_not_break():
    score = calculate_valuation_score(10, float("nan"), 1)
    assert not math.isnan(score)
    assert 0 <= score <= 1


def test_valuation_score_in_range():
    for pe in (5, 10, 50, 500):
        assert 0 <= calculate_valuation_score(pe, 1.5, 1) <= 1


def test_composite_score_fills_missing_with_0_5():
    df = pd.DataFrame({
        "code": ["A", "B"],
        "date": pd.to_datetime(["2026-01-05", "2026-01-05"]),
        "total_technical_score": [0.8, np.nan],
        "total_financial_score": [np.nan, 0.6],
        "valuation_score": [np.nan, np.nan],
    })
    out = calculate_composite_score(df, horizon="medium")
    w = HORIZON_WEIGHTS["medium"]
    expected_a = 0.8 * w["tech"] + 0.5 * w["fin"] + 0.5 * w["val"]
    expected_b = 0.5 * w["tech"] + 0.6 * w["fin"] + 0.5 * w["val"]
    assert np.isclose(out.loc[out["code"] == "A", "total_composite_score"].iloc[0], expected_a)
    assert np.isclose(out.loc[out["code"] == "B", "total_composite_score"].iloc[0], expected_b)
    assert sorted(out["composite_rank"].unique()) == [1, 2]


def test_unknown_horizon_falls_back_to_medium():
    df = pd.DataFrame({
        "code": ["A"],
        "date": pd.to_datetime(["2026-01-05"]),
        "total_technical_score": [0.5],
        "total_financial_score": [0.5],
        "valuation_score": [0.5],
    })
    out = calculate_composite_score(df, horizon="bogus")
    w = HORIZON_WEIGHTS["medium"]
    assert np.isclose(out["total_composite_score"].iloc[0], 0.5 * (w["tech"] + w["fin"] + w["val"]))


def test_build_composite_factor_uses_latest_available_report():
    technical = pd.DataFrame({
        "code": ["A", "A", "B", "B"],
        "date": pd.to_datetime(["2026-01-05", "2026-02-02", "2026-01-05", "2026-02-02"]),
        "total_technical_score": [0.8, 0.7, 0.6, 0.5],
    })
    financial = pd.DataFrame({
        "code": ["A", "A", "B"],
        "report_date": pd.to_datetime(["2025-12-31", "2026-01-20", "2025-12-31"]),
        "total_financial_score": [0.5, 0.9, 0.4],
        "pe_ttm": [10.0, 20.0, 15.0],
        "pb": [1.5, 2.0, 1.0],
        "peg": [1.0, 1.0, 1.0],
    })
    out = build_composite_factor(technical, financial, horizon="medium")

    assert set(["code", "date", "total_composite_score", "composite_rank", "valuation_score"]) <= set(out.columns)
    # A 在 2026-02-02 应使用 2026-01-20 的最新财报（score 0.9）
    a_feb = out[(out["code"] == "A") & (out["date"] == "2026-02-02")].iloc[0]
    assert np.isclose(a_feb["total_financial_score"], 0.9)
    # A 在 2026-01-05 只能取到 2025-12-31 的财报（score 0.5）
    a_jan = out[(out["code"] == "A") & (out["date"] == "2026-01-05")].iloc[0]
    assert np.isclose(a_jan["total_financial_score"], 0.5)
