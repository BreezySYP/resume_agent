"""research/technical_diagnostics.py — 技术因子诊断：IC 分布 / 分层 / 多空 / 因子与收益分布"""
import matplotlib.pyplot as plt
import pandas as pd
from research.common import load_technical_and_price, prepare_future_return
from research.technical_backtest import calc_quantile_return

FIG_DIR = "./data/technical_diagnostics_fig/"


def calculate_ic_series(df):
    return df.groupby("date").apply(lambda x: x["total_technical_score"].corr(x["future_return"], method="spearman"))


def quantile_analysis(df):
    result = calc_quantile_return(df, n_quantiles=10).mean(axis=0)
    plt.figure(figsize=(10, 5))
    result.plot(kind="bar")
    plt.title("Future Return by Quantile")
    plt.savefig(FIG_DIR + "future_return_by_quantile.png")
    return result


def long_short_test(df):
    df = df.copy()
    df["quantile"] = df.groupby("date")["total_technical_score"].transform(lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))
    top = df[df["quantile"] == 9].groupby("date")["future_return"].mean()
    bottom = df[df["quantile"] == 0].groupby("date")["future_return"].mean()
    spread = top - bottom
    nav = (1 + spread.fillna(0)).cumprod()
    plt.figure(figsize=(12, 6))
    nav.plot()
    plt.title("Long Top10% / Short Bottom10%")
    plt.savefig(FIG_DIR + "long_top10_short_bottom10.png")
    return spread


def factor_distribution(df):
    plt.figure(figsize=(10, 6))
    df["total_technical_score"].hist(bins=100)
    plt.title("Factor Distribution")
    plt.savefig(FIG_DIR + "factor_distribution.png")


def return_distribution(df):
    plt.figure(figsize=(10, 6))
    df["future_return"].clip(-1, 1).hist(bins=100)
    plt.title("Future Return Distribution")
    plt.savefig(FIG_DIR + "return_distribution.png")


def run(hold_days: int = 20):
    factor_df, price_df = load_technical_and_price()
    merged = prepare_future_return(factor_df, price_df, hold_days)

    ic_series = calculate_ic_series(merged)
    print("IC describe:\n", ic_series.describe())
    print("IC > 0 比例:", (ic_series > 0).mean())

    quantile_analysis(merged)
    long_short_test(merged)
    factor_distribution(merged)
    return_distribution(merged)


if __name__ == "__main__":
    run()
