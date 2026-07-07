from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field
import pipeline_single_stock as pp


router = APIRouter(prefix="/api/etl", tags=["ETL 任务"])

class TriggerResponse(BaseModel):
    # job_ids: List[int]
    message: str


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
def trigger_stock_etl(req: TriggerStockRequest):
    pp.run_code_pipeline(req.code, req.steps)
    return TriggerResponse(message="Finished run steps for code")