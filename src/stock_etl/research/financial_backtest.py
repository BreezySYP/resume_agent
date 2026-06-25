"""research/financial_backtest.py — 财务因子回测：财报生效日对齐 + IC + 分层 + TopN 组合"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shared.db.mysql import engine


def factor_backtest(factor_df: pd.DataFrame, price_df: pd.DataFrame, hold_days: int = 20, top_n: int = 100) -> dict:
    factor_df = factor_df.copy()
    factor_df["code"] = factor_df["code"].str[2:]
    factor_df["report_date"] = pd.to_datetime(factor_df["report_date"])
    factor_df["effective_date"] = factor_df["report_date"] + pd.Timedelta(days=30)  # 财报公布后约 30 天生效
    price_df["date"] = pd.to_datetime(price_df["date"])

    merged = pd.merge_asof(
        price_df.sort_values("date"), factor_df.sort_values("effective_date"),
        left_on="date", right_on="effective_date", by="code", direction="backward",
    )
    merged["future_return"] = merged.groupby("code")["close"].shift(-hold_days) / merged["close"] - 1
    merged = merged.dropna(subset=["total_score", "future_return"])

    # IC
    daily_ic = []
    for _, group in merged.groupby("date"):
        if len(group) < 30:
            continue
        ic, _ = spearmanr(group["total_score"], group["future_return"])
        if not np.isnan(ic):
            daily_ic.append(ic)
    ic_series = pd.Series(daily_ic)
    ic_mean, ic_std = ic_series.mean(), ic_series.std()
    ic_ir = ic_mean / ic_std if ic_std > 0 else np.nan

    # 分层收益
    merged["quantile"] = merged.groupby("date")["total_score"].transform(lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))
    quantile_return = merged.groupby("quantile")["future_return"].mean()

    # Top N 组合
    merged["rank"] = merged.groupby("date")["total_score"].rank(ascending=False, method="first")
    merged["next_day_return"] = merged.groupby("code")["close"].pct_change().shift(-1)
    portfolio_return = merged[merged["rank"] <= top_n].groupby("date")["next_day_return"].mean().fillna(0)
    nav = (1 + portfolio_return).cumprod()

    benchmark = price_df.groupby("date")["close"].mean().pct_change().fillna(0)
    benchmark_nav = (1 + benchmark).cumprod()

    drawdown = nav / nav.cummax() - 1
    annual_return = nav.iloc[-1] ** (252 / len(nav)) - 1

    print(f"IC Mean: {ic_mean:.4f}  IC IR: {ic_ir:.4f}")
    print(f"Annual Return: {annual_return * 100:.2f}%  Max Drawdown: {drawdown.min() * 100:.2f}%  Final NAV: {nav.iloc[-1]:.2f}")

    plt.figure(figsize=(10, 5))
    quantile_return.plot(kind="bar")
    plt.title("Quantile Return")
    plt.ylabel("Future Return")
    plt.savefig("./data/financial_fig/quantile_return.png")

    plt.figure(figsize=(14, 6))
    plt.plot(nav.index, nav.values, label=f"Top {top_n}")
    plt.plot(benchmark_nav.index, benchmark_nav.values, label="Benchmark")
    plt.legend()
    plt.title("Factor Strategy NAV")
    plt.ylabel("Net Value")
    plt.grid()
    plt.savefig("./data/financial_fig/factor_strategy_nav.png")

    return {"merged": merged, "nav": nav, "benchmark_nav": benchmark_nav, "ic_mean": ic_mean, "ic_ir": ic_ir, "annual_return": annual_return, "max_drawdown": drawdown.min()}


if __name__ == "__main__":
    factor_df = pd.read_sql("SELECT * FROM financial_factor", engine)
    price_df = pd.read_sql("SELECT * FROM history", engine)
    factor_backtest(factor_df, price_df, hold_days=20, top_n=100)
