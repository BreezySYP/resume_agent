"""routers/etl.py — ETL 触发 & SSE 进度推送"""
from __future__ import annotations
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from loguru import logger

from shared.db.mysql import get_db
from services.etl_service import (
    STEPS_META,
    PER_STOCK_STEPS,
    DAILY_STEPS,
    SEASON_STEPS,
    create_job,
    run_step_async,
    sse_stream,
    get_running_jobs,
    get_job_logs,
    trigger_stock_etl
)

router = APIRouter(prefix="/api/etl", tags=["ETL 任务"])


# ── Request / Response Models ─────────────────────────────────────────────────

class TriggerStockRequest(BaseModel):
    code:  str        = Field(..., description="股票代码，如 600519")
    steps: List[str]  = Field(..., description=f"可选 step: {list(PER_STOCK_STEPS)}")


class TriggerAllRequest(BaseModel):
    mode:  str        = Field("daily", description="daily 或 season")
    steps: Optional[List[str]] = Field(None, description="自定义 step 列表，为空则按 mode 默认")


class TriggerResponse(BaseModel):
    # job_ids: List[int]
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/steps",
    summary="获取所有可用 step 定义",
    description="返回所有 step 的名称、中文标签、分组（daily/season）以及是否支持单股触发。",
)
def list_steps():
    return [
        {
            "step":          step,
            "label":         meta["label"],
            "group":         meta["group"],
            "per_stock":     step in PER_STOCK_STEPS,
        }
        for step, meta in STEPS_META.items()
    ]


@router.get(
    "/jobs/running",
    summary="获取当前运行中的任务",
    description="返回所有 pending / running 状态的任务列表。",
)
def running_jobs(db: Session = Depends(get_db)):
    return get_running_jobs(db)


@router.get(
    "/jobs/logs",
    summary="查询任务历史日志",
    description="按股票代码和/或 step 过滤历史执行记录，默认返回最近 100 条。",
)
def job_logs(
    code:  Optional[str] = Query(None, description="股票代码，为空返回所有"),
    step:  Optional[str] = Query(None, description="step 名称，为空返回所有"),
    limit: int           = Query(100, ge=1, le=500, description="返回条数"),
    db:    Session = Depends(get_db),
):
    return get_job_logs(db, code=code, step=step, limit=limit)


@router.delete(
    "/jobs/{job_id}",
    summary="取消/删除任务记录",
    description="将指定任务标记为 failed（running 状态的任务不会被强制停止，仅更新记录）。",
)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text
    db.execute(
        text("UPDATE etl_job_log SET status='failed', error_msg='用户手动取消' WHERE id=:id"),
        {"id": job_id}
    )
    db.commit()
    return {"message": f"job {job_id} 已标记为取消"}