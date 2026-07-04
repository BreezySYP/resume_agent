"""storage/checkpoint.py — ETL 断点续跑：按 step 记录 start_date / start_code / last_completed"""
import datetime
from dataclasses import dataclass

from sqlalchemy import text
from shared.db.mysql import engine


@dataclass
class CodeCheckpoint:
    code: str
    step: str | None = None
    start_at: str | None = None
    completed_at: datetime.datetime | None = None


def get_code_checkpoint(code: str, step: str) -> CodeCheckpoint:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT code, step, start_at, completed_at, etl_checkpoint WHERE code = :code AND step = :step"),
            {"code": code, "step": step},
        ).fetchone()
    if row is None:
        return CodeCheckpoint(code=code)
    return CodeCheckpoint(
        code= code,
        step= step,
        start_at: str(row[1]) if row[1] else None,
        completed_at: str(row[2]) if row[2] else None
    )


def is_completed_today(code: str) -> bool:
    cp = get_code_checkpoint(code, step)
    # 如果 last_completed_at 是今天下午4点之后，则认为今天已经完成
    if cp.completed_at is not None:
        now = datetime.datetime.now()
        if now.day - cp.completed_at.day < 1 and ((cp.completed_at.hour >= 16 and now.hour >= 16) or (cp.completed_at.hour < 16 and now.hour < 16)):
            return True
    return False


def save_checkpoint(code, step: str, start_at: datetime.datetime | None = None) -> None:
    """写入进度断点（on_progress 回调用），未传入的字段保持原值"""
    sql = text("""
        INSERT INTO etl_code_checkpoint (code, step, start_at)
        VALUES (:code, :step, :start_at)
        ON DUPLICATE KEY UPDATE
            step = COALESCE(:step, step),
            start_at = COALESCE(:start_at, start_at)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"code": code, "step": step, "start_at": start_at})


def clear_checkpoint(step: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM etl_code_checkpoint WHERE code = :code"), {"code": code})


