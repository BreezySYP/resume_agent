"""services/etl_service.py — ETL 任务触发 & 状态管理"""
from __future__ import annotations
import asyncio
import datetime
import importlib
import sys
import os
from typing import List, Callable, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger

# ETL step 定义（和 pipeline.py 保持一致）
STEPS_META = {
    "history":             {"label": "历史K线",  "group": "daily"},
    "technical":           {"label": "技术因子",  "group": "daily"},
    "financial_statement": {"label": "财务报表",  "group": "season"},
    "financial_feature":   {"label": "财务特征",  "group": "season"},
    "financial_factor":    {"label": "财务因子",  "group": "season"},
    "composite":           {"label": "综合因子",  "group": "season"},
    "capital_hot":         {"label": "资金热点",  "group": "daily"},
    "profile":             {"label": "公司简介",  "group": "daily"},
    "news":                {"label": "新闻",      "group": "daily"},
    "qdrant_news_sync":    {"label": "新闻向量同步", "group": "daily"},
    "qdrant_profile_sync": {"label": "简介向量同步", "group": "daily"},
}

# 单股可触发的 step（全局类 step 不支持单股）
PER_STOCK_STEPS = ["history", "financial_statement", "profile", "news"]

# 全量触发组合
DAILY_STEPS  = ["history", "technical", "capital_hot", "profile", "news",
                 "qdrant_profile_sync", "qdrant_news_sync"]
SEASON_STEPS = ["history", "technical", "financial_statement", "financial_feature",
                "financial_factor", "composite", "capital_hot", "profile", "news",
                "qdrant_profile_sync", "qdrant_news_sync"]

# SSE 事件队列（全局，按 job_id 索引）
_sse_queues: dict[int, asyncio.Queue] = {}


def create_job(db: Session, code: str, step: str, triggered_by: str = "manual") -> int:
    """在 etl_job_log 创建一条 pending 记录，返回 job_id"""
    sql = text("""
        INSERT INTO etl_job_log (code, step, status, triggered_by)
        VALUES (:code, :step, 'pending', :triggered_by)
    """)
    with db.begin():
        result = db.execute(sql, {"code": code, "step": step, "triggered_by": triggered_by})
        return result.lastrowid


def update_job(db: Session, job_id: int, status: str,
               row_count: int = 0, error_msg: str = None) -> None:
    now = datetime.datetime.now()
    if status == "running":
        sql = text("""
            UPDATE etl_job_log SET status='running', started_at=:now WHERE id=:id
        """)
        db.execute(sql, {"now": now, "id": job_id})
    else:
        sql = text("""
            UPDATE etl_job_log
            SET status=:status, finished_at=:now,
                duration_ms = TIMESTAMPDIFF(SECOND, started_at, :now) * 1000,
                row_count=:row_count, error_msg=:error_msg
            WHERE id=:id
        """)
        db.execute(sql, {
            "status": status, "now": now,
            "row_count": row_count, "error_msg": error_msg, "id": job_id
        })
    db.commit()


async def _push_event(job_id: int, code: str, step: str,
                      status: str, message: str, progress: float = None):
    """推送 SSE 事件到对应队列"""
    if job_id in _sse_queues:
        await _sse_queues[job_id].put({
            "job_id": job_id, "code": code, "step": step,
            "status": status, "message": message, "progress": progress,
        })


async def run_step_async(db: Session, job_id: int,
                          code: str, step: str) -> None:
    """在线程池里执行同步的 pipeline step，通过 SSE 推送进度"""
    _sse_queues[job_id] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    await _push_event(job_id, code, step, "running", f"开始执行 {step}")
    update_job(db, job_id, "running")

    def _run():
        pipeline = _get_pipeline()
        step_fn  = pipeline.STEPS.get(step)
        if step_fn is None:
            raise ValueError(f"未知 step: {step}")

        # 单股模式：修改环境变量让 step 只处理指定 code
        if code != "ALL" and step in PER_STOCK_STEPS:
            if step in ("profile", "news"):
                step_fn(min_code=code)
            elif step == "history":
                step_fn()   # history 通过 checkpoint 续跑
            elif step == "financial_statement":
                step_fn(start_code=int(code), end_code=int(code) + 1)
        else:
            step_fn()

    try:
        await loop.run_in_executor(None, _run)
        update_job(db, job_id, "success")
        await _push_event(job_id, code, step, "success", f"{step} 执行完成", 1.0)
    except Exception as e:
        error = str(e)
        logger.error("job {} {} {} 失败: {}", job_id, code, step, error)
        update_job(db, job_id, "failed", error_msg=error)
        await _push_event(job_id, code, step, "failed", f"{step} 失败: {error}")
    finally:
        # 标记队列结束
        await _sse_queues[job_id].put(None)


async def sse_stream(job_id: int) -> AsyncGenerator[str, None]:
    """SSE 生成器：监听指定 job 的事件队列"""
    import json
    queue = _sse_queues.get(job_id)
    if queue is None:
        yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
        return

    while True:
        event = await queue.get()
        if event is None:
            yield f"data: {json.dumps({'done': True})}\n\n"
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"


def get_running_jobs(db: Session) -> list:
    sql = text("""
        SELECT id, code, step, status, triggered_by,
               started_at, finished_at, duration_ms, row_count, error_msg
        FROM etl_job_log
        WHERE status IN ('pending', 'running')
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = db.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


def get_job_logs(db: Session, code: str = None,
                  step: str = None, limit: int = 100) -> list:
    where_clauses = []
    params = {"limit": limit}
    if code:
        where_clauses.append("code = :code")
        params["code"] = code
    if step:
        where_clauses.append("step = :step")
        params["step"] = step
    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    sql = text(f"""
        SELECT id, code, step, status, triggered_by,
               started_at, finished_at, duration_ms, row_count, error_msg
        FROM etl_job_log {where}
        ORDER BY id DESC LIMIT :limit
    """)
    rows = db.execute(sql, params).mappings().fetchall()
    return [dict(r) for r in rows]

PER_STOCK_STEPS = ["history", "profile", "news"]

import requests

url = "http://host.docker.internal:8011/api/etl/trigger/stock"

def trigger_stock_etl(code:str, steps: List[str]):
    response = requests.post(url, json={"code": code, "steps": steps})
    if response.status_code == 200:
        return "OK"

if __name__ == "__main__":
    print(trigger_stock_etl("000004", ["profile", "news"]))