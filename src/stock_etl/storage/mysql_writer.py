"""storage/mysql_writer.py — ETL 写入 MySQL 的统一入口"""
import pandas as pd
from sqlalchemy import text
from shared.db.mysql import save_dataframe, WriteMethod, engine


def save_history(df: pd.DataFrame) -> int:
    return save_dataframe(df, "history", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_technical_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "technical_factor", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_financial_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_factor", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_financial_feature(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_feature", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_stock_factor(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_factor", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_capital_flow(df: pd.DataFrame) -> int:
    return save_dataframe(df, "capital_flow", if_exists="append")


def save_hot_sectors(df: pd.DataFrame) -> int:
    return save_dataframe(df, "hot_sectors", if_exists="append")


def save_financial_statement(df: pd.DataFrame) -> int:
    return save_dataframe(df, "financial_statement", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_stock_profile(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_profile", if_exists="append", method=WriteMethod.INSERT_UPSERT)


def save_stock_business_breakdown(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_business_breakdown", if_exists="append", method=WriteMethod.INSERT_IGNORE)


def save_stock_news(df: pd.DataFrame) -> int:
    return save_dataframe(df, "stock_news", if_exists="append", method=WriteMethod.INSERT_IGNORE)


if __name__ == "__main__":
    df = pd.DataFrame([{"code": "999999", "business": "have fun", "scope": "all day have fun!", "name": "hahaha"}])
    save_stock_profile(df)
    print("before: ", pd.read_sql("SELECT * FROM stock_profile WHERE code = '999999'", con=engine.connect()))
    df = pd.DataFrame([{"code": "999999", "business": "have fun again", "scope": "all day have fun again!", "name": "hahaha"}])
    save_stock_profile(df)
    print("after: ", pd.read_sql("SELECT * FROM stock_profile WHERE code = '999999'", con=engine.connect()))
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM stock_profile WHERE code = :code"), {"code": 999999})