"""shared/db/mysql.py — MySQL 连接池 + 通用查询工具，ETL 与 Agent 共用"""
from enum import Enum

import pandas as pd
import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import sessionmaker

from shared.configs.settings import (
    MYSQL_DB,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_ROOT_USER,
)

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

_pool: PooledDB | None = None


def _get_pool() -> PooledDB:
    """惰性创建连接池：import 阶段不连接 MySQL，首次使用时才建连。"""
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql, maxconnections=6, mincached=0, maxcached=5, blocking=True,
            host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_ROOT_USER,
            password=MYSQL_PASSWORD, database=MYSQL_DB, charset="utf8mb4",
        )
        logger.info("db pool ready")
    return _pool

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

    
def get_connection():
    return _get_pool().connection()


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


# ==================== 1. 定义写入方法枚举 ====================

class WriteMethod(Enum):
    """MySQL 写入方法枚举"""
    INSERT_IGNORE = "insert_ignore"  # 重复则跳过
    INSERT_UPSERT = "insert_upsert"  # 重复则更新
    REPLACE = "replace"              # 重复则替换（DELETE + INSERT）
    APPEND = "append"                # 普通追加（重复会报错）


# ==================== 2. 实现各种写入方法 ====================

def insert_ignore_method(table, conn, keys, data_iter):
    """INSERT IGNORE：重复则跳过"""
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = mysql_insert(table.table).prefix_with("IGNORE")
    result = conn.execute(stmt, data)
    return result.rowcount


def insert_upsert_method(table, conn, keys, data_iter):
    """INSERT ... ON DUPLICATE KEY UPDATE：重复则更新所有字段"""
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = mysql_insert(table.table).values(data)
    
    # 更新所有字段
    update_dict = {key: getattr(stmt.inserted, key) for key in keys}
    stmt = stmt.on_duplicate_key_update(**update_dict)
    
    result = conn.execute(stmt)
    return result.rowcount


def replace_method(table, conn, keys, data_iter):
    """REPLACE INTO：重复则删除后重新插入"""
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = mysql_insert(table.table).values(data).prefix_with("REPLACE")
    result = conn.execute(stmt)
    return result.rowcount


def append_method(table, conn, keys, data_iter):
    """普通追加：使用 multi 方式批量插入（重复会报错）"""
    data = [dict(zip(keys, row)) for row in data_iter]
    stmt = mysql_insert(table.table).values(data)
    result = conn.execute(stmt)
    return result.rowcount


# ==================== 3. 方法映射 ====================

WRITE_METHOD_MAP = {
    WriteMethod.INSERT_IGNORE: insert_ignore_method,
    WriteMethod.INSERT_UPSERT: insert_upsert_method,
    WriteMethod.REPLACE: replace_method,
    WriteMethod.APPEND: append_method,
}


# ==================== 4. 统一保存函数 ====================

def save_dataframe(
    df: pd.DataFrame, 
    table: str, 
    if_exists: str = "append", 
    chunksize: int = 5000, 
    method: WriteMethod = WriteMethod.APPEND,
    update_timestamp: bool = False  # 是否强制更新时间戳
) -> int:
    """
    统一的 DataFrame -> MySQL 写入入口
    
    Args:
        df: 要写入的 DataFrame
        table: 表名
        if_exists: 表存在时的处理方式 ('append', 'replace', 'fail')
        chunksize: 批次大小
        method: 写入方法 (WriteMethod 枚举)
        update_timestamp: 是否强制更新 completed_at（仅对 INSERT_UPSERT 有效）
    
    Returns:
        写入的行数
    
    Examples:
        >>> save_dataframe(df, "users", method=WriteMethod.INSERT_UPSERT)
        >>> save_dataframe(df, "etl_checkpoint", method=WriteMethod.INSERT_IGNORE)
    """
    sql_method = WRITE_METHOD_MAP.get(method, append_method)
    
    # 执行写入
    result = df.to_sql(
        table, 
        engine,  # 需要在外部定义或传入
        if_exists=if_exists,
        index=False, 
        chunksize=chunksize, 
        method=sql_method
    )
    
    logger.info("✅ saved {} rows to `{}` (method={}, update_timestamp={})", 
                result, table, method.value, update_timestamp)
    return len(df)
