from core.db import engine
import pandas as pd
import numpy as np
from jobs.data_loader import load_df


# =====================================================
# LOAD DATA
# =====================================================

def load_data():

    sql = """
    SELECT
        code,
        name,
        date,
        open,
        high,
        low,
        close,
        volume
    FROM history
    """

    df = load_df(sql, "history")

    df["date"] = pd.to_datetime(df["date"])

    df = (
        df
        .sort_values(["code", "date"])
        .reset_index(drop=True)
    )

    return df


# =====================================================
# INDICATORS
# =====================================================

def rsi(close, window=14):

    delta = close.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window).mean()

    avg_loss = loss.rolling(window).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def momentum(close, window):

    return close / close.shift(window) - 1


def obv(close, volume):

    direction = np.sign(close.diff()).fillna(0)

    return (direction * volume).cumsum()


def mfi(high, low, close, volume, window=14):

    tp = (high + low + close) / 3

    mf = tp * volume

    pos_flow = mf.where(tp.diff() > 0, 0)

    neg_flow = mf.where(tp.diff() < 0, 0)

    pos_sum = pos_flow.rolling(window).sum()

    neg_sum = neg_flow.rolling(window).sum()

    mfr = pos_sum / neg_sum.replace(0, np.nan)

    return 100 - 100 / (1 + mfr)


def ema(series, span):

    return series.ewm(span=span, adjust=False).mean()


def macd(close):

    ema12 = ema(close, 12)

    ema26 = ema(close, 26)

    macd_line = ema12 - ema26

    signal = macd_line.ewm(span=9, adjust=False).mean()

    hist = macd_line - signal

    return hist


# =====================================================
# FACTOR BUILD
# =====================================================

def build_technical_factor(df):

    result = []

    for code, g in df.groupby("code"):

        g = g.copy()

        # ---------------------------
        # trend
        # ---------------------------

        g["ma20_ratio"] = (
            g["close"] /
            g["close"].rolling(20).mean()
        )

        g["ma60_ratio"] = (
            g["close"] /
            g["close"].rolling(60).mean()
        )

        g["ma120_ratio"] = (
            g["close"] /
            g["close"].rolling(120).mean()
        )

        # ---------------------------
        # momentum
        # ---------------------------

        g["rsi14"] = rsi(g["close"], 14)

        g["mom20"] = momentum(g["close"], 20)

        g["macd_hist"] = macd(g["close"])

        # ---------------------------
        # volume
        # ---------------------------

        g["obv"] = obv(
            g["close"],
            g["volume"]
        )

        g["mfi14"] = mfi(
            g["high"],
            g["low"],
            g["close"],
            g["volume"],
            14
        )

        result.append(g)

    df = pd.concat(result)

    # =================================================
    # CROSS SECTION RANK
    # =================================================

    rank_cols = [
        "ma20_ratio",
        "ma60_ratio",
        "ma120_ratio",
        "rsi14",
        "mom20",
        "macd_hist",
        "obv",
        "mfi14"
    ]

    for col in rank_cols:

        df[col + "_rank"] = (
            df
            .groupby("date")[col]
            .rank(pct=True)
        )

    # =================================================
    # SCORE
    # =================================================

    df["trend_score"] = (
        df["ma20_ratio_rank"] * 0.3 +
        df["ma60_ratio_rank"] * 0.3 +
        df["ma120_ratio_rank"] * 0.4
    )

    df["momentum_score"] = (
        df["rsi14_rank"] * 0.3 +
        df["mom20_rank"] * 0.4 +
        df["macd_hist_rank"] * 0.3
    )

    df["volume_score"] = (
        df["obv_rank"] * 0.5 +
        df["mfi14_rank"] * 0.5
    )

    df["total_technical_score"] = (
        df["trend_score"] * 0.4 +
        df["momentum_score"] * 0.4 +
        df["volume_score"] * 0.2
    )

    df["technical_rank"] = (
        df.groupby("date")["total_technical_score"]
        .rank(
            ascending=False,
            method="min"
        )
    )

    return df[
        [
            "code",
            "name",
            "date",

            "trend_score",
            "momentum_score",
            "volume_score",

            "total_technical_score",
            "technical_rank"
        ]
    ]


# =====================================================
# SAVE
# =====================================================

def save(df):

    df.to_sql(
        "technical_factor",
        engine,
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi"
    )


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("load data...")

    # df = load_data()
    df = pd.read_csv("./src/stock_agent/jobs/temp_history.csv")

    print("build factor...")

    factor_df = build_technical_factor(df)

    print("save...")

    save(factor_df)
    
    print(f"saved rows = {len(factor_df)}")