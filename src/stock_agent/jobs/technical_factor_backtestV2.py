import pandas as pd
import numpy as np

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

def add_regime(df, q=0.8):

    threshold = df["total_technical_score"].quantile(q)

    df = df.copy()

    df["regime"] = np.where(
        df["total_technical_score"] >= threshold,
        "extreme",
        "normal"
    )

    return df
# =========================
# 1. IC / RankIC
# =========================
def calc_ic(df):
    ic = df.groupby("date").apply(
        lambda x: x["total_technical_score"].corr(x["future_return"])
    )
    return ic.mean()


def calc_rankic(df):
    rankic = df.groupby("date").apply(
        lambda x: x["total_technical_score"].corr(x["future_return"], method="spearman")
    )
    return rankic.mean()


# =========================
# 2. 分层收益（Quantile）
# =========================
def calc_quantile_return(df, n_quantiles=5):

    df = df.copy()
    df["quantile"] = df.groupby("date")["total_technical_score"] \
                       .transform(lambda x: pd.qcut(x, n_quantiles, labels=False, duplicates="drop"))

    q_ret = df.groupby(["date", "quantile"])["future_return"].mean().unstack()

    return q_ret


# =========================
# 3. Long Short Alpha
# =========================
def calc_long_short(df, top_n=20):

    df = df.copy()

    def get_ls(group):
        top = group.nlargest(top_n, "total_technical_score")
        bottom = group.nsmallest(top_n, "total_technical_score")
        return top["future_return"].mean() - bottom["future_return"].mean()

    ls = df.groupby("date").apply(get_ls)
    nav = (1 + ls).cumprod()

    return ls, nav


# =========================
# 4. Turnover（交易成本核心）
# =========================
def calc_turnover(df, top_n=20):

    df = df.sort_values(["date", "total_technical_score"])

    def get_top_codes(x):
        return set(x.nlargest(top_n, "total_technical_score")["code"])

    portfolio = df.groupby("date").apply(get_top_codes)

    turnover = portfolio.shift().combine(portfolio, lambda prev, cur:
                                         len(cur - prev) / top_n if prev else 0)

    return turnover


# =========================
# 5. 主策略（normal + extreme）
# =========================
def dual_strategy_backtest(df, top_n=20):

    df = df.copy()

    # ========== NORMAL ==========
    normal = df[df["regime"] == "normal"]

    normal_ls, normal_nav = calc_long_short(normal, top_n)

    # ========== EXTREME ==========
    extreme = df[df["regime"] == "extreme"]

    extreme_ls, extreme_nav = calc_long_short(extreme, top_n)

    # ========== COMBINE ==========
    combined = pd.concat(
        [normal_ls.rename("normal"),
         extreme_ls.rename("extreme")],
        axis=1
    ).fillna(0)

    total_ls = combined.mean(axis=1)
    total_nav = (1 + total_ls).cumprod()

    return {
        "normal_nav": normal_nav,
        "extreme_nav": extreme_nav,
        "total_nav": total_nav,
        "ic": calc_ic(df),
        "rankic": calc_rankic(df),
    }
    
if __name__ == "__main__":

    print("======== LOAD DATA ========")
    factor_df, price_df = load_data()

    print("======== PREPARE DATA ========")
    merged = prepare_data(factor_df, price_df, hold_days=20)

    merged = add_regime(merged)

    print("merged rows:", len(merged))

    print(dual_strategy_backtest(merged))