import asyncio
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from constants import DAILY_STEPS, SEASON_STEPS, STEPS_META, ETL_QUEUE_PREFIX
from services.etl_service import run_all, push_event, run_code
from shared.db.redis import sse_stream
from uuid import uuid4

router = APIRouter(prefix="/api/etl", tags=["ETL 任务"])

class TriggerResponse(BaseModel):
    job_ids: list[str]
    message: str

class TriggerAllRequest(BaseModel):
    mode:  str        = Field("daily", description="daily 或 season")
    job_id: str       = Field(str(uuid4()), description="任务 ID，默认随机生成")    
    steps: Optional[List[str]] = Field(None, description="自定义 step 列表，为空则按 mode 默认")


PER_STOCK_STEPS = ["history", "profile", "news"]
class TriggerStockRequest(BaseModel):
    code:  str        = Field(..., description="股票代码，如 600519")
    steps: List[str]  = Field(..., description=f"可选 step: {list(PER_STOCK_STEPS)}")

@router.post(
    "/trigger/stock", 
    response_model=TriggerResponse,
    description=f"""
        为指定股票触发一个或多个 ETL step。

        支持单股触发的 step：`{PER_STOCK_STEPS}`

        触发后返回 job_ids，可通过 `/api/etl/stream/{{job_id}}` 订阅 SSE 实时进度。
    """)
def trigger_stock_etl(
    req: TriggerStockRequest,
    background: BackgroundTasks 
):
    
    job_id = str(uuid4())
    background.add_task(run_code, job_id, req.code, req.steps)
    return TriggerResponse(job_ids=[job_id], message="Finished run steps for code")

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
async def stream_job(job_id: str):
    return StreamingResponse(
        sse_stream(job_id, ETL_QUEUE_PREFIX),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


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
    req: TriggerAllRequest,
    background: BackgroundTasks
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

    background.add_task(run_all, req.job_id, steps)
    return TriggerResponse(
        job_ids=[req.job_id],
        message=f"已创建 {len([req.job_id])} 个全量任务（mode={req.mode}）"
    )
