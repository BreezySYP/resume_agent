import os

import pandas as pd
from core.db import engine
from data.coderule import add_prefix

DATA_CSV_MAP = {
    "history": "./src/stock_agent/jobs/data/history.csv",
    "technical_factor": "./src/stock_agent/jobs/data/technical_factor.csv",
    "financial_factor": "./src/stock_agent/jobs/data/financial_factor.csv",
    "stock_factor": "./src/stock_agent/jobs/data/stock_factor.csv",
    "stock_industry": "./src/stock_agent/jobs/data/stock_industry.csv",
    "stock_news": "./src/stock_agent/jobs/data/stock_news.csv",
    "stock_profile": "./src/stock_agent/jobs/data/stock_profile.csv",
    "stock_business_breakdown": "./src/stock_agent/jobs/data/stock_business_breakdown.csv"
}

def normalize(df: pd.DataFrame):
    df["code"] = df["code"].apply(lambda x: add_prefix(str(x).zfill(6)))
    df = df.rename(columns={"report_date": "date"})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df
def load_df(sql, map_name):
    if os.path.isfile(DATA_CSV_MAP[map_name]):
        df = pd.read_csv(DATA_CSV_MAP[map_name])
        if not df.empty:
            return normalize(df)

    df = pd.read_sql(sql, engine)


    df.to_csv(DATA_CSV_MAP[map_name])
    return normalize(df)