"""storage/mysql_writer.py — ETL 写入 MySQL 的统一入口"""
import os

import pandas as pd
from shared.db.mysql import engine, save_dataframe

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_CSV_MAP = {
    "history": os.path.join(DATA_DIR, "history.csv"),
    "technical_factor": os.path.join(DATA_DIR, "technical_factor.csv"),
    "financial_factor": os.path.join(DATA_DIR, "financial_factor.csv"),
    "stock_factor": os.path.join(DATA_DIR, "stock_factor.csv"),
    "stock_industry": os.path.join(DATA_DIR, "stock_industry.csv"),
    "stock_news": os.path.join(DATA_DIR, "stock_news.csv"),
    "stock_profile": os.path.join(DATA_DIR, "stock_profile.csv"),
    "stock_business_breakdown": os.path.join(DATA_DIR, "stock_business_breakdown.csv"),
}


def save_history(df: pd.DataFrame) -> int:
    return save_dataframe(df, "history", if_exists="append")


def save_technical_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "technical_factor", if_exists="replace")


def save_financial_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_factor", if_exists="replace")


def save_financial_feature(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_feature", if_exists="replace")


def save_stock_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_factor", if_exists="replace")


def save_capital_flow(df: pd.DataFrame) -> int:
    return save_dataframe(df, "capital_flow", if_exists="append")


def save_hot_sectors(df: pd.DataFrame) -> int:
    return save_dataframe(df, "hot_sectors", if_exists="append")


def save_financial_statement(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_statement", if_exists="append", ignore_duplicates=True)


def save_stock_profile(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_profile", if_exists="append", ignore_duplicates=True)


def save_stock_business_breakdown(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_business_breakdown", if_exists="append", ignore_duplicates=True)


def save_stock_news(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_news", if_exists="append")
