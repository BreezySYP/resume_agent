"""research/technical_backtest.py — 技术因子回测：IC / RankIC / 分层收益 / 多空 / 换手率 / 双策略组合"""
import matplotlib.pyplot as plt
import pandas as pd
from research.common import add_regime, load_technical_and_price, prepare_future_return

FIG_DIR = "./data/technical_fig/"


def calc_ic(df: pd.DataFrame) -> float:
    return df.groupby("date").apply(lambda x: x["total_technical_score"].corr(x["future_return"])).mean()


def calc_rank_ic(df: pd.DataFrame) -> float:
    return df.groupby("date").apply(lambda x: x["total_technical_score"].corr(x["future_return"], method="spearman")).mean()


def calc_quantile_return(df: pd.DataFrame, n_quantiles: int = 5) -> pd.DataFrame:
    df = df.copy()
    df["quantile"] = df.groupby("date")["total_technical_score"].transform(lambda x: pd.qcut(x, n_quantiles, labels=False, duplicates="drop"))
    return df.groupby(["date", "quantile"])["future_return"].mean().unstack()


def calc_long_short(df: pd.DataFrame, top_n: int = 20) -> tuple[pd.Series, pd.Series]:
    def get_ls(group):
        top = group.nlargest(top_n, "total_technical_score")
        bottom = group.nsmallest(top_n, "total_technical_score")
        return top["future_return"].mean() - bottom["future_return"].mean()

    ls = df.groupby("date").apply(get_ls)
    return ls, (1 + ls).cumprod()


def calc_turnover(df: pd.DataFrame, top_n: int = 20) -> pd.Series:
    df = df.sort_values(["date", "total_technical_score"])
    portfolio = df.groupby("date").apply(lambda x: set(x.nlargest(top_n, "total_technical_score")["code"]))
    return portfolio.shift().combine(portfolio, lambda prev, cur: len(cur - prev) / top_n if prev else 0)


def dual_strategy_backtest(df: pd.DataFrame, top_n: int = 20) -> dict:
    """normal 区间均值回归（买低分） + extreme 区间动量（买高分）"""
    normal = df[df["regime"] == "normal"]
    extreme = df[df["regime"] == "extreme"]
    normal_ls, normal_nav = calc_long_short(normal, top_n)
    extreme_ls, extreme_nav = calc_long_short(extreme, top_n)
    combined = pd.concat([normal_ls.rename("normal"), extreme_ls.rename("extreme")], axis=1).fillna(0)
    total_nav = (1 + combined.mean(axis=1)).cumprod()
    return {"normal_nav": normal_nav, "extreme_nav": extreme_nav, "total_nav": total_nav, "ic": calc_ic(df), "rankic": calc_rank_ic(df)}


def top_n_nav(df: pd.DataFrame, top_n: int = 20) -> pd.Series:
    df = df.copy()
    df["rank"] = df.groupby("date")["total_technical_score"].rank(ascending=False, method="first")
    portfolio_return = df[df["rank"] <= top_n].groupby("date")["future_return"].mean().fillna(0)
    return (1 + portfolio_return).cumprod()


def run(hold_days: int = 20, top_n: int = 20) -> dict:
    factor_df, price_df = load_technical_and_price()
    merged = add_regime(prepare_future_return(factor_df, price_df, hold_days))
    result = dual_strategy_backtest(merged, top_n)

    plt.figure(figsize=(12, 6))
    result["normal_nav"].plot(label="Normal (Reversion)")
    result["extreme_nav"].plot(label="Extreme (Momentum)")
    result["total_nav"].plot(label="Combined")
    plt.legend()
    plt.title("Dual Strategy NAV")
    plt.savefig(FIG_DIR + "dual_strategy_nav.png")

    print(f"IC mean: {result['ic']:.4f}, RankIC mean: {result['rankic']:.4f}")
    return result


if __name__ == "__main__":
    run()
