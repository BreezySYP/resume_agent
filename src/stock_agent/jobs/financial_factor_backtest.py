import pandas as pd
import numpy as np

from scipy.stats import spearmanr
from matplotlib import pyplot as plt


# =====================================
# 因子回测
# =====================================

def factor_backtest(
    factor_df,
    price_df,
    hold_days=20,
    top_n=100
):

    print("======== PREPARE DATA ========")

    factor_df = factor_df.copy()
    price_df = price_df.copy()
    factor_df["code"] = factor_df['code'].str[2:]

    factor_df["report_date"] = pd.to_datetime(
        factor_df["report_date"]
    )

    price_df["date"] = pd.to_datetime(
        price_df["date"]
    )

    factor_df = factor_df.sort_values(
        ["code", "report_date"]
    )

    price_df = price_df.sort_values(
        ["code", "date"]
    )
    
    # ----------------------------------
    # 财报生效日期
    # ----------------------------------

    factor_df["effective_date"] = (
        factor_df["report_date"]
        + pd.Timedelta(days=30)
    )
    # ----------------------------------
    # merge_asof
    # ----------------------------------

    merged = pd.merge_asof(
        price_df.sort_values("date"),
        factor_df.sort_values("effective_date"),
        left_on="date",
        right_on="effective_date",
        by="code",
        direction="backward"
    )

    print("merged rows:", len(merged))

    # =====================================
    # Future Return
    # =====================================

    print("======== FUTURE RETURN ========")

    merged["future_return"] = (
        merged.groupby("code")["close"]
        .shift(-hold_days)
        / merged["close"]
        - 1
    )

    merged = merged.dropna(
        subset=[
            "total_score",
            "future_return"
        ]
    )

    # =====================================
    # IC
    # =====================================

    print("======== IC TEST ========")

    daily_ic = []

    for date, group in merged.groupby("date"):

        if len(group) < 30:
            continue

        try:

            ic, _ = spearmanr(
                group["total_score"],
                group["future_return"]
            )

            if not np.isnan(ic):
                daily_ic.append(ic)

        except:
            pass

    ic_series = pd.Series(daily_ic)

    ic_mean = ic_series.mean()

    ic_std = ic_series.std()

    ic_ir = (
        ic_mean / ic_std
        if ic_std > 0
        else np.nan
    )

    print()
    print("IC Mean :", round(ic_mean, 4))
    print("IC IR   :", round(ic_ir, 4))

    # =====================================
    # 分层回测
    # =====================================

    print()
    print("======== QUANTILE TEST ========")

    merged["quantile"] = (
        merged.groupby("date")["total_score"]
        .transform(
            lambda x:
            pd.qcut(
                x,
                10,
                labels=False,
                duplicates="drop"
            )
        )
    )

    quantile_return = (
        merged.groupby("quantile")["future_return"]
        .mean()
    )

    print()
    print(quantile_return)

    plt.figure(figsize=(10, 5))

    quantile_return.plot(
        kind="bar"
    )

    plt.title(
        "Quantile Return"
    )

    plt.ylabel(
        "Future Return"
    )

    plt.show()

    # =====================================
    # Top N组合
    # =====================================

    print()
    print("======== TOP N STRATEGY ========")

    merged["rank"] = (
        merged.groupby("date")["total_score"]
        .rank(
            ascending=False,
            method="first"
        )
    )

    merged["selected"] = (
        merged["rank"] <= top_n
    )

    merged["next_day_return"] = (
        merged.groupby("code")["close"]
        .pct_change()
        .shift(-1)
    )

    portfolio_return = (
        merged[
            merged["selected"]
        ]
        .groupby("date")[
            "next_day_return"
        ]
        .mean()
    )

    portfolio_return = portfolio_return.fillna(0)

    nav = (
        1 +
        portfolio_return
    ).cumprod()

    # =====================================
    # Benchmark
    # =====================================

    benchmark = (
        price_df.groupby("date")["close"]
        .mean()
        .pct_change()
        .fillna(0)
    )

    benchmark_nav = (
        1 +
        benchmark
    ).cumprod()

    # =====================================
    # Max Drawdown
    # =====================================

    rolling_max = nav.cummax()

    drawdown = (
        nav
        /
        rolling_max
        - 1
    )

    max_drawdown = drawdown.min()

    # =====================================
    # Annual Return
    # =====================================

    total_days = len(nav)

    annual_return = (
        nav.iloc[-1]
        **
        (252 / total_days)
        - 1
    )

    # =====================================
    # 输出结果
    # =====================================

    print()
    print("Annual Return :",
          round(annual_return * 100, 2),
          "%")

    print("Max Drawdown :",
          round(max_drawdown * 100, 2),
          "%")

    print("Final NAV :",
          round(nav.iloc[-1], 2))

    # =====================================
    # Plot NAV
    # =====================================

    plt.figure(figsize=(14, 6))

    plt.plot(
        nav.index,
        nav.values,
        label=f"Top {top_n}"
    )

    plt.plot(
        benchmark_nav.index,
        benchmark_nav.values,
        label="Benchmark"
    )

    plt.legend()

    plt.title(
        "Factor Strategy NAV"
    )

    plt.ylabel(
        "Net Value"
    )

    plt.grid()

    plt.show()

    return {
        "merged": merged,
        "nav": nav,
        "benchmark_nav": benchmark_nav,
        "ic_mean": ic_mean,
        "ic_ir": ic_ir,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown
    }


# =====================================
# main
# =====================================

if __name__ == "__main__":

    from core.db import engine

    factor_df = pd.read_sql(
        """
        select *
        from financial_factor
        """,
        engine
    )

    price_df = pd.read_sql(
        """
        select *
        from history
        """,
        engine
    )

    result = factor_backtest(
        factor_df,
        price_df,
        hold_days=20,
        top_n=100
    )

    print(result)