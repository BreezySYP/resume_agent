"""storage/mysql_writer.py — ETL 写入 MySQL 的统一入口"""
import pandas as pd
from shared.db.mysql import save_dataframe


def save_history(df: pd.DataFrame) -> int:
    return save_dataframe(df, "history", if_exists="append", ignore_duplicates=True)


def save_technical_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "technical_factor", if_exists="append", ignore_duplicates=True)


def save_financial_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_factor", if_exists="append", ignore_duplicates=True)


def save_financial_feature(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_feature", if_exists="append", ignore_duplicates=True)


def save_stock_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_factor", if_exists="append", ignore_duplicates=True)


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
    return save_dataframe(df, "stock_news", if_exists="append", ignore_duplicates=True)