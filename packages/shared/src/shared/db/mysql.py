"""shared/db/mysql.py — MySQL 连接池 + 通用查询工具，ETL 与 Agent 共用"""
import pandas as pd
import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from shared.configs.settings import MYSQL_DB, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_ROOT_USER

logger.info("Connecting to MySQL: {}@{}:{}/{}", MYSQL_ROOT_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)

engine = create_engine(
    f"mysql+pymysql://{MYSQL_ROOT_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}",
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
        "init_command": (
            "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,"
            "NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
        ),
    },
)

pool = PooledDB(
    creator=pymysql, maxconnections=6, mincached=2, maxcached=5, blocking=True,
    host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_ROOT_USER,
    password=MYSQL_PASSWORD, database=MYSQL_DB, charset="utf8mb4",
)


def get_connection():
    return pool.connection()


def get_tables() -> list[str]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]


def get_schema() -> list[str]:
    with engine.connect() as conn:
        parts = []
        for (table,) in conn.execute(text("SHOW TABLES")).fetchall():
            cols = conn.execute(text(f"DESCRIBE `{table}`")).fetchall()
            col_defs = ", ".join(f"{c[0]} {c[1]}" for c in cols)
            parts.append(f"- {table}({col_defs})")
        return parts


def execute_query(sql: str, max_rows: int = 100) -> list[dict]:
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("只允许 SELECT 查询")
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchmany(max_rows)]


def get_dataframe(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def insert_ignore(table, conn, keys, data_iter):
    """pandas to_sql method：重复则跳过"""
    data = [dict(zip(keys, row)) for row in data_iter]
    conn.execute(mysql_insert(table.table).prefix_with("IGNORE"),   )


def save_dataframe(df: pd.DataFrame, table: str, if_exists: str = "append", chunksize: int = 5000, ignore_duplicates: bool = False) -> int:
    """统一的 DataFrame -> MySQL 写入入口，ETL job 应优先使用此方法而非直接调用 to_sql"""
    method = insert_ignore if ignore_duplicates else "multi"
    df.to_sql(table, engine, if_exists=if_exists, index=False, chunksize=chunksize, method=method)
    logger.info("✅ saved {} rows to `{}` (if_exists={})", len(df), table, if_exists)
    return len(df)





