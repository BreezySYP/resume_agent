import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from jobs.data_loader import load_df

rootdir = "./src/stock_agent/jobs/data/technical_diagnostics_fig/"
# ============================================
# LOAD
# ============================================

def load_data():

    factor_df = load_df("""
        SELECT
            code,
            date,
            total_technical_score
        FROM technical_factor
    """, "technical_factor")

    price_df = load_df("""
        SELECT
            code,
            date,
            close
        FROM history
    """, "history")

    factor_df["date"] = pd.to_datetime(
        factor_df["date"]
    )

    price_df["date"] = pd.to_datetime(
        price_df["date"]
    )

    return factor_df, price_df


# ============================================
# PREPARE
# ============================================

def prepare_data(
    factor_df,
    price_df,
    hold_days=20
):

    price_df = (
        price_df
        .sort_values(
            ["code", "date"]
        )
        .copy()
    )

    price_df["future_close"] = (
        price_df
        .groupby("code")["close"]
        .shift(-hold_days)
    )

    price_df["future_return"] = (
        price_df["future_close"]
        /
        price_df["close"]
        - 1
    )

    merged = factor_df.merge(
        price_df[
            [
                "code",
                "date",
                "future_return"
            ]
        ],
        on=["code", "date"],
        how="inner"
    )

    merged = merged.dropna(
        subset=[
            "total_technical_score",
            "future_return"
        ]
    )

    return merged


# ============================================
# IC
# ============================================

def calculate_ic(df):

    ic_series = (
        df.groupby("date")
        .apply(
            lambda x:
            x["total_technical_score"]
            .corr(
                x["future_return"],
                method="spearman"
            )
        )
    )

    print("\n========== IC ==========")

    print(ic_series.describe())

    print("\nIC > 0 比例:")
    print(
        (
            ic_series > 0
        ).mean()
    )

    plt.figure(figsize=(12, 6))

    ic_series.hist(
        bins=50
    )

    plt.title(
        "IC Distribution"
    )

    plt.savefig(rootdir+"IC Distribution")

    return ic_series


# ============================================
# RANK IC
# ============================================

def calculate_rank_ic(df):

    rank_ic = (
        df.groupby("date")
        .apply(
            lambda x:
            x["total_technical_score"]
            .rank()
            .corr(
                x["future_return"].rank()
            )
        )
    )

    print("\n========== Rank IC ==========")

    print(rank_ic.describe())

    print(
        "\nRankIC > 0 比例:"
    )

    print(
        (rank_ic > 0).mean()
    )

    return rank_ic


# ============================================
# QUANTILE
# ============================================

def quantile_analysis(df):

    df = df.copy()

    df["quantile"] = (
        df.groupby("date")
        ["total_technical_score"]
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

    result = (
        df.groupby("quantile")
        ["future_return"]
        .mean()
    )

    print("\n========== QUANTILE ==========")

    print(
        
    )

    plt.figure(figsize=(10, 5))

    result.plot(
        kind="bar"
    )

    plt.title(
        "Future Return by Quantile"
    )

    plt.savefig(rootdir+"Future Return by Quantile")

    return result


# ============================================
# LONG SHORT
# ============================================

def long_short_test(df):

    df = df.copy()

    df["quantile"] = (
        df.groupby("date")
        ["total_technical_score"]
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

    top = (
        df[df["quantile"] == 9]
        .groupby("date")
        ["future_return"]
        .mean()
    )

    bottom = (
        df[df["quantile"] == 0]
        .groupby("date")
        ["future_return"]
        .mean()
    )

    spread = top - bottom

    print(
        "\n========== LONG SHORT =========="
    )

    print(
        spread.describe()
    )

    print(
        "\n平均超额收益:"
    )

    print(
        spread.mean()
    )

    nav = (
        1 +
        spread.fillna(0)
    ).cumprod()

    plt.figure(figsize=(12, 6))

    nav.plot()

    plt.title(
        "Long Top10% / Short Bottom10%"
    )


    plt.savefig(rootdir+"Long Top10% Short Bottom10%")

    return spread


# ============================================
# FACTOR DISTRIBUTION
# ============================================

def factor_distribution(df):

    print(
        "\n========== FACTOR DISTRIBUTION =========="
    )

    print(
        df["total_technical_score"]
        .describe()
    )

    plt.figure(figsize=(10, 6))

    df[
        "total_technical_score"
    ].hist(
        bins=100
    )

    plt.title(
        "Factor Distribution"
    )

    plt.savefig(rootdir+"Factor Distribution")


# ============================================
# RETURN DISTRIBUTION
# ============================================

def return_distribution(df):

    print(
        "\n========== RETURN DISTRIBUTION =========="
    )

    print(
        df["future_return"]
        .describe(
            percentiles=[
                0.01,
                0.05,
                0.5,
                0.95,
                0.99
            ]
        )
    )

    plt.figure(figsize=(10, 6))

    df[
        "future_return"
    ].clip(
        -1,
        1
    ).hist(
        bins=100
    )

    plt.title(
        "Future Return Distribution"
    )

    plt.savefig(rootdir+"Future Return Distribution")


# ============================================
# STABILITY
# ============================================


def factor_stability(df):

    daily_mean = (
        df.groupby("date")
        ["total_technical_score"]
        .mean()
    )

    daily_std = (
        df.groupby("date")
        ["total_technical_score"]
        .std()
    )

    print(
        "\n========== STABILITY =========="
    )

    print(
        "Mean score std:",
        daily_mean.std()
    )

    print(
        "Cross-sectional std mean:",
        daily_std.mean()
    )

    plt.figure(figsize=(12, 6))

    daily_mean.plot(
        label="Mean"
    )

    daily_std.plot(
        label="Std"
    )

    plt.legend()

    plt.savefig(rootdir+"Mean Std")


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    factor_df, price_df = load_data()

    df = prepare_data(
        factor_df,
        price_df,
        hold_days=20
    )

    print(
        "\nRows:",
        len(df)
    )

    calculate_ic(df)

    calculate_rank_ic(df)

    quantile_analysis(df)

    long_short_test(df)

    factor_distribution(df)

    return_distribution(df)

    factor_stability(df)
