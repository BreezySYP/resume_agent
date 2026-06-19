import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from core.db import engine
from data.coderule import add_prefix
from jobs.data_loader import load_df

rootdir = "./src/stock_agent/jobs/data/technical_fig/"
# =====================================================

# LOAD

# =====================================================

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
        FROM history """, "history")
   
    factor_df["date"] = pd.to_datetime(factor_df["date"])
    price_df["date"] = pd.to_datetime(price_df["date"])

    return factor_df, price_df

# =====================================================

# PREPARE

# =====================================================

def prepare_data(factor_df, price_df, hold_days=20):
    price_df = (
        price_df
        .sort_values(["code", "date"])
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

    def format_code(code):
        return add_prefix(str(code).zfill(6))

    # factor_df["code"] = factor_df["code"].apply(format_code)

    merged = factor_df.merge(
        price_df[
            [
                "code",
                "date",
                "close",
                "future_return"
            ]
        ],
        on=["code", "date"],
        how="inner"
    )
    merged = factor_df.merge(
        price_df[["code", "date", "close", "future_return"]],
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

# =====================================================

# IC TEST

# =====================================================

def calculate_ic(df):
    from scipy.stats import kendalltau

    def ic(g):
        return kendalltau(
            g["total_technical_score"].rank(),
            g["future_return"].rank()
        )[0]

    return df.groupby("date").apply(ic)

def add_regime(df, q=0.8):

    threshold = df["total_technical_score"].quantile(q)

    df = df.copy()

    df["regime"] = np.where(
        df["total_technical_score"] >= threshold,
        "extreme",
        "normal"
    )

    return df

def dual_strategy_backtest(df, top_n=20):

    df = df.copy()

    # ========== STRATEGY A: normal (mean reversion) ==========
    normal = df[df["regime"] == "normal"]

    normal["rank"] = normal.groupby("date")["total_technical_score"].rank()

    # 反向做：买低分
    normal_selected = normal.groupby("date", group_keys=False).apply(
        lambda x: x.nsmallest(top_n, "total_technical_score"))

    normal_portfolio = normal_selected.groupby("date")["future_return"].mean()
    normal_nav = (1 + normal_portfolio).cumprod()

    # ========== STRATEGY B: extreme (momentum) ==========
    extreme = df[df["regime"] == "extreme"]

    extreme["rank"] = extreme.groupby("date")["total_technical_score"].rank(ascending=False)

    extreme_selected = extreme.groupby("date", group_keys=False).apply(
        lambda x: x.nlargest(top_n, "total_technical_score"))

    extreme_portfolio = extreme_selected.groupby("date")["future_return"].mean()
    extreme_nav = (1 + extreme_portfolio).cumprod()

    # ========== COMBINE ==========
    combined = pd.concat([
        normal_portfolio.rename("normal"),
        extreme_portfolio.rename("extreme")
    ], axis=1).fillna(0)

    combined["total"] = combined.mean(axis=1)

    total_nav = (1 + combined["total"]).cumprod()

    return normal_nav, extreme_nav, total_nav
# =====================================================

# QUANTILE TEST

# =====================================================

def quantile_test(df):

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

    print()
    print("======== QUANTILE TEST ========")
    print()
    print(result)

    result.plot(
        kind="bar",
        figsize=(10,5)
    )

    plt.title(
        "Future Return by Quantile"
    )

    plt.savefig(rootdir + "Future Return by Quantile")

    return result

# =====================================================

# TOP N STRATEGY

# =====================================================

def top_n_backtest(
    df,
    top_n=20
    ):

    df = df.copy()

    df["rank"] = (
        df.groupby("date")
        ["total_technical_score"]
        .rank(
            ascending=False,
            method="first"
        )
    )

    selected = (
        df["rank"] <= top_n
    )

    portfolio = (
        df[selected]
        .groupby("date")
        ["future_return"]
        .mean()
    )

    nav = (
        1 + portfolio
    ).cumprod()

    annual_return = (
        nav.iloc[-1]
        **
        (252 / len(nav))
        - 1
    )

    drawdown = (
        nav /
        nav.cummax()
        - 1
    )

    max_drawdown = (
        drawdown.min()
    )

    print()
    print("======== TOP N STRATEGY ========")
    print()
    print(
        "Annual Return :",
        round(
            annual_return * 100,
            2
        ),
        "%"
    )

    print(
        "Max Drawdown :",
        round(
            max_drawdown * 100,
            2
        ),
        "%"
    )

    print(
        "Final NAV :",
        round(
            nav.iloc[-1],
            2
        )
    )

    plt.figure(figsize=(12,6))

    nav.plot(
        label=f"Top {top_n}"
    )

    plt.legend()

    plt.title(
        "TopN Strategy NAV"
    )

    plt.savefig(rootdir + "TopN Strategy NAV")

    return nav

# =====================================================

# BENCHMARK

# =====================================================

def benchmark_nav(price_df):
    benchmark = (
        price_df
        .groupby("date")
        ["close"]
        .mean()
    )

    benchmark = (
        benchmark /
        benchmark.iloc[0]
    )

    return benchmark

# =====================================================

# MAIN

# =====================================================

def split_ic(df):

    q = df["future_return"].quantile(0.99)

    normal = df[df["future_return"] <= q]
    extreme = df[df["future_return"] > q]

    def ic(g):
        return g["total_technical_score"].rank().corr(
            g["future_return"].rank()
        )

    print("normal_ic " + str(ic(normal)))
    print("extreme_ic " + str(ic(extreme)))
    # return {
    #     "normal_ic": ic(normal),
    #     "extreme_ic": ic(extreme)
    # }

if __name__ == "__main__":

    print("======== LOAD DATA ========")
    factor_df, price_df = load_data()

    print("======== PREPARE DATA ========")
    merged = prepare_data(factor_df, price_df, hold_days=20)

    print("merged rows:", len(merged))

    # ========== ADD REGIME ==========
    merged = add_regime(merged, q=0.8)

    # ========== IC ==========
    ic_series = calculate_ic(merged)

    print("IC mean:", ic_series.mean())

    # ========== BACKTEST ==========
    normal_nav, extreme_nav, total_nav = dual_strategy_backtest(merged)

    # ========== PLOT ==========
    plt.figure(figsize=(12,6))

    normal_nav.plot(label="Normal (Reversion)")
    extreme_nav.plot(label="Extreme (Momentum)")
    total_nav.plot(label="Combined")

    plt.legend()
    plt.title("Dual Strategy NAV")
    plt.savefig(rootdir + "dual_strategy_nav.png")