"""routers/status.py — checkpoint 状态查询"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.db.mysql import get_db
from services.etl_service import STEPS_META

router = APIRouter(prefix="/api/status", tags=["ETL 状态"])


@router.get(
    "/checkpoints",
    summary="获取所有 step 的 checkpoint 状态",
    description="""
从 `etl_checkpoint` 表读取每个 step 的断点信息：
- `start_date`：当前增量起始日期
- `start_code`：断点续跑的股票代码（中断时保存）
- `last_completed_date`：最后一次全部完成的日期
- `last_completed_at`：最后一次完成的时间戳
    """,
)
def get_checkpoints(db: Session = Depends(get_db)):
    sql = text("""
        SELECT step, start_date, start_code, last_completed_date, last_completed_at
        FROM etl_checkpoint
        ORDER BY step
    """)
    rows = db.execute(sql).mappings().fetchall()
    result = {r["step"]: dict(r) for r in rows}

    for step in STEPS_META:
        if step not in result:
            result[step] = {
                "step":                step,
                "start_date":          None,
                "start_code":          None,
                "last_completed_date": None,
                "last_completed_at":   None,
            }
    return result


@router.get(
    "/checkpoints/{step}",
    summary="获取指定 step 的 checkpoint",
    description="返回单个 step 的完整断点信息。",
)
def get_checkpoint(step: str, db: Session = Depends(get_db)):
    sql  = text("""
        SELECT step, start_date, start_code, last_completed_date, last_completed_at
        FROM etl_checkpoint WHERE step = :step
    """)
    row = db.execute(sql, {"step": step}).mappings().fetchone()
    if row is None:
        return {"step": step, "start_date": None, "start_code": None,
                "last_completed_date": None, "last_completed_at": None}
    return dict(row)


@router.delete(
    "/checkpoints/{step}",
    summary="清除指定 step 的 checkpoint",
    description="清除断点后，下次执行该 step 会从头开始（等价于全量重跑）。",
)
def clear_checkpoint(step: str, db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM etl_checkpoint WHERE step = :step"), {"step": step})
    db.commit()
    return {"message": f"{step} checkpoint 已清除"}


@router.get(
    "/summary",
    summary="ETL 整体健康状态",
    description="""
        汇总视图，一次性返回：
        - 各 step 的 checkpoint 状态
        - 各 step 最近一次执行的成功/失败状态
        - 当前运行中的任务数量
    """,
)
def get_summary(db: Session = Depends(get_db)):
    cp_rows = db.execute(text(
        "SELECT step, start_date, start_code, last_completed_date, last_completed_at "
        "FROM etl_checkpoint ORDER BY step"
    )).mappings().fetchall()
    checkpoints = {r["step"]: dict(r) for r in cp_rows}

    job_rows = db.execute(text("""
        SELECT step, status, finished_at, row_count, error_msg
        FROM etl_job_log
        WHERE id IN (SELECT MAX(id) FROM etl_job_log GROUP BY step, code)
          AND code = 'ALL'
        ORDER BY step
    """)).mappings().fetchall()
    jobs = {r["step"]: dict(r) for r in job_rows}

    running_count = db.execute(text(
        "SELECT COUNT(*) FROM etl_job_log WHERE status IN ('pending','running')"
    )).scalar() or 0

    result = {}
    for step, meta in STEPS_META.items():
        result[step] = {
            "step":        step,
            "label":       meta["label"],
            "group":       meta["group"],
            "checkpoint":  checkpoints.get(step),
            "last_job":    jobs.get(step),
        }

    return {
        "steps":         result,
        "running_count": running_count,
    }