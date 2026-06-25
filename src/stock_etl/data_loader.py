"""data_loader.py — 带本地 CSV 缓存的数据加载器（避免重复查询 MySQL）"""
import os

import pandas as pd
from sqlalchemy import text
from shared.code_rule import add_prefix
from shared.db.mysql import engine
# from storage.mysql_writer import DATA_CSV_MAP


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df["code"] = df["code"].apply(lambda x: add_prefix(str(x).zfill(6)))
    df = df.rename(columns={"report_date": "date"})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_df(sql: str, table: str) -> pd.DataFrame:
    """优先读取本地 CSV 缓存，没有则查询 MySQL 并写入缓存"""
    # csv_path = DATA_CSV_MAP[table]
    # if os.path.isfile(csv_path):
    #     df = pd.read_csv(csv_path)
    #     if not df.empty:
    #         return normalize(df)
    df = pd.read_sql(text(sql), engine)
    # os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    # df.to_csv(csv_path, index=False)
    # return normalize(df)
    return df
