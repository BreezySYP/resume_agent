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


@router.post(
    "/trigger/stock",
    response_model=TriggerResponse,
    summary="触发单股 ETL 下载",
    description=f"""
        为指定股票触发一个或多个 ETL step。

        支持单股触发的 step：`{PER_STOCK_STEPS}`

        触发后返回 job_ids，可通过 `/api/etl/stream/{{job_id}}` 订阅 SSE 实时进度。
    """,
)
async def trigger_stock(
    req:        TriggerStockRequest,
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
):
    result = trigger_stock_etl(code=req.code, steps=req.steps)
    if result == "OK":
        return TriggerResponse(
            message="OK"
        )
    else:
        raise HTTPException(status_code=500, detail=f"wrong request")


@router.post(
    "/trigger/all",
    response_model=TriggerResponse,
    summary="总开关：触发全量 ETL",
    description="""
触发全量 ETL pipeline。

- `mode=daily`：执行每日 step（history / technical / capital_hot / profile / news / qdrant sync）
- `mode=season`：执行季报 step（包含 financial_statement / feature / factor / composite）
- 也可以通过 `steps` 字段自定义 step 列表

触发后返回 job_ids，可通过 `/api/etl/stream/{job_id}` 订阅 SSE 实时进度。
    """,
)
async def trigger_all(
    req:        TriggerAllRequest,
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
):
    if req.steps:
        steps = req.steps
    elif req.mode == "season":
        steps = SEASON_STEPS
    else:
        steps = DAILY_STEPS

    invalid = [s for s in steps if s not in STEPS_META]
    if invalid:
        raise HTTPException(status_code=400, detail=f"未知 step: {invalid}")

    job_ids = []
    for step in steps:
        job_id = create_job(db, code="ALL", step=step, triggered_by="all")
        job_ids.append(job_id)
        background.add_task(run_step_async, db, job_id, "ALL", step)

    return TriggerResponse(
        job_ids=job_ids,
        message=f"已创建 {len(job_ids)} 个全量任务（mode={req.mode}）"
    )


@router.get(
    "/stream/{job_id}",
    summary="SSE 实时进度订阅",
    description="""
            通过 Server-Sent Events (SSE) 订阅指定任务的实时进度。

            连接后会持续收到事件，直到任务完成或失败。

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
        """,
        response_class=StreamingResponse,
    )
async def stream_job(job_id: int):
    return StreamingResponse(
        sse_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


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