"""storage/checkpoint.py — ETL 断点续跑：按 step 记录 start_date / start_code / last_completed"""
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy import text
from shared.db.mysql import engine


@dataclass
class CodeCheckpoint:
    code: str
    step: str | None = None
    start_at: str | None = None
    completed_at: datetime | None = None


def get_code_checkpoint(code: str, step: str) -> CodeCheckpoint:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT code, step, start_at, completed_at from etl_code_checkpoint WHERE code = :code AND step = :step"),
            {"code": code, "step": step},
        ).fetchone()
    if row is None:
        return CodeCheckpoint(code=code)
    return CodeCheckpoint(
        code=code,
        step=step,
        start_at=str(row[2]) if row[1] else None,
        completed_at= row[3] if row[2] else None
    )

def get_next_8am(dt):
    # 构造当天 8:00 的时间
    today_8am = dt.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # 如果当前时间 <= 今天 8:00，返回今天 8:00
    if dt <= today_8am:
        return today_8am
    else:
        # 否则返回明天 8:00
        return today_8am + timedelta(days=1)
    
def is_completed_today(code: str, step: str) -> bool:
    cp = get_code_checkpoint(code, step)
    # 如果 last_completed_at 是今天下午4点之后，则认为今天已经完成
    if cp.completed_at is None:
        return False
    now = datetime.now()
    return get_next_8am(cp.completed_at) > now


def save_checkpoint(code, step: str, start_at: str | None = None) -> None:
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


def clear_checkpoint(code:str, step: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM etl_code_checkpoint WHERE code = :code"), {"code": code, "step": step})

if __name__ == "__main__":
    # save_checkpoint("999999", "hahahaha", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # print(get_code_checkpoint("999999", "hahahaha"))
    # print(is_completed_today("999999", "hahahaha"))
    # clear_checkpoint("999999", "hahahaha")
    print(datetime.now())
    print(get_next_8am(datetime(2026, 7, 6, 0, 23, 33)))
    print(get_next_8am( datetime(2026, 7, 6, 9, 52, 47)))
