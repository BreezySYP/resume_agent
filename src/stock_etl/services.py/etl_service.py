import math

from pipeline_single_stock import run_code_pipeline, run_pipeline, get_codes
from shared.db.redis import push_queue
from uuid import uuid4

def push_event(job_id: str, code: str, step: str, status: str, message: str, progress: float):
    """推送事件到 Redis 队列"""
    push_queue({ 
        "job_id": job_id,
        "code": code,
        "step": step,
        "status": status,
        "message": message,
        "progress": progress
    })

def run_all_pipeline(job_id: str, steps: list[str]) -> None:
    """
    触发全量 ETL pipeline
    事件格式：
        ```json
        {
        "job_id": 1,
        "code": "600519",
        "step": "history",
        "status": "running|success|failed",
        "message": "描述信息",
        "progress": 0.5
        }
        ```
    """
    codes = get_codes()
    total = len(codes) * len(steps)
    completed = 0
    for code, name in codes:
        for step in steps:
            push_event(job_id, code, step, "running",
                        f"处理{code} {name} {step} 中", 
                        math.round(completed / total, 2))
            msg = f"{code} {name} {step} 处理完成"
            try:
                result = run_code_pipeline(code, step)
                status = "success" if result else "failed"
            except Exception as e:
                result = False
                msg = f"{code} {step} 处理失败: {e}"
                status = "failed"
            push_event(job_id, code, step, status, 
                       msg, math.round(completed / total, 2))
            completed += 1
    push_event(job_id, "ALL", "ALL", "success", 
               f"全量 ETL pipeline 完成，共处理 {total} 个任务", 1.0)