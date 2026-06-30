"""storage/checkpoint.py — ETL 断点续跑：按 step 记录 start_date / start_code / last_completed"""
import datetime
from dataclasses import dataclass

from sqlalchemy import text
from shared.db.mysql import engine


@dataclass
class Checkpoint:
    step: str
    start_date: str | None = None
    start_code: str | None = None
    last_completed_date: str | None = None
    last_completed_at: datetime.datetime | None = None


def get_checkpoint(step: str) -> Checkpoint:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT start_date, start_code, last_completed_date, last_completed_at FROM etl_checkpoint WHERE step = :step"),
            {"step": step},
        ).fetchone()
    if row is None:
        return Checkpoint(step=step)
    return Checkpoint(
        step=step,
        start_date=str(row[0]) if row[0] else None,
        start_code=row[1],
        last_completed_date=str(row[2]) if row[2] else None,
        last_completed_at=row[3],
    )


def is_completed_today(step: str) -> bool:
    cp = get_checkpoint(step)
    # 如果 last_completed_at 是今天下午4点之后，则认为今天已经完成
    if cp.last_completed_at is not None:
        now = datetime.datetime.now()
        if now.day - cp.last_completed_at.day < 1 and ((cp.last_completed_at.hour >= 16 and now.hour >= 16) or (cp.last_completed_at.hour < 16 and now.hour < 16)):
            return True
    return False


def save_checkpoint(step: str, start_date: str | None = None, start_code: str | None = None) -> None:
    """写入进度断点（on_progress 回调用），未传入的字段保持原值"""
    sql = text("""
        INSERT INTO etl_checkpoint (step, start_date, start_code)
        VALUES (:step, :start_date, :start_code)
        ON DUPLICATE KEY UPDATE
            start_date = COALESCE(:start_date, start_date),
            start_code = COALESCE(:start_code, start_code)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"step": step, "start_date": start_date, "start_code": start_code})


def mark_completed(step: str) -> None:
    """step 全部完成后调用：记录完成日期+时间，清除 start_code，保留 start_date"""
    now = datetime.datetime.now()
    sql = text("""
        INSERT INTO etl_checkpoint (step, last_completed_date, last_completed_at, start_code)
        VALUES (:step, :today, :now, NULL)
        ON DUPLICATE KEY UPDATE
            last_completed_date = :today,
            last_completed_at   = :now,
            start_code          = NULL
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"step": step, "today": now.date(), "now": now})


def clear_checkpoint(step: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM etl_checkpoint WHERE step = :step"), {"step": step})


