"""services/etl_service.py — ETL 任务触发 & 事件推送"""
from constants import ETL_QUEUE_PREFIX
from services.pipeline_single_stock import get_codes, run_code_pipeline
from shared.db.redis import push_queue


def push_event(job_id: str, code: str, step: str, status: str, message: str, progress: float, done: bool = False):
    """推送事件到 Redis 队列"""
    push_queue(job_id, {
        "job_id": job_id,
        "code": code,
        "step": step,
        "status": status,
        "done": done,
        "message": message,
        "progress": progress,
    }, ETL_QUEUE_PREFIX)


def run_all(job_id: str, steps: list[str]) -> None:
    """触发全量 ETL pipeline。"""
    codes = get_codes()
    total = len(codes) * len(steps)
    completed = 0
    for code, name in codes:
        for step in steps:
            push_event(job_id, code, step, "running",
                       f"处理{code} {name} {step} 中",
                       round(completed / total, 2), False)
            msg = f"{code} {name} {step} 处理完成"
            try:
                result = run_code_pipeline(code, step)
                status = "success" if result else "failed"
            except Exception as e:
                result = False
                msg = f"{code} {name} {step} 处理失败: {e}"
                status = "failed"
            push_event(job_id, code, step, status,
                       msg, round(completed / total, 2), False)
            completed += 1
    push_event(job_id, "ALL", "ALL", "success",
               f"全量 ETL pipeline 完成，共处理 {total} 个任务", 1.0, True)


def run_code(job_id: str, code: str, steps: list[str]):
    """触发单只股票的 ETL step，失败时推送 failed 事件。"""
    completed = 0
    total = len(steps)
    for step in steps:
        push_event(job_id, code, step, "running",
                   f"处理{code} {step} 中",
                   round(completed / total, 2), False)
        try:
            run_code_pipeline(code, step)
            push_event(job_id, code, step, "success",
                       f"处理{code} {step} 完成",
                       round(completed / total, 2), True)
        except Exception as e:
            push_event(job_id, code, step, "failed",
                       f"处理{code} {step} 失败: {e}",
                       round(completed / total, 2), True)
        completed += 1
