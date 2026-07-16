from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.graph import ask_investment
from event.queue_manager import sse_stream

router = APIRouter(prefix="/api/ai", tags=["AI tasks"])

class TriggerAgentReponse(BaseModel):
    thread_id: str
    message: str

class TriggerAgentRequest(BaseModel):
    thread_id: str
    question: str


@router.post(
    "/qa",
    response_model=TriggerAgentReponse,
    summary="发送股票相关问题给agent",
    description=f"""
        触发一次ai agent  QA
    """
)
async def triggerAgent(
    qa: TriggerAgentRequest,
    background: BackgroundTasks
):
    background.add_task(ask_investment, qa.question, qa.thread_id)
    return TriggerAgentReponse(
        thread_id=qa.thread_id,
        message="ai stock agent is triggered for the question"
    )

@router.get(
    "/qa/stream/{thread_id}",
    summary="订阅ai agent的回答",
    description=f"""
        订阅ai agent的状态
    """
)
async def stream_agent(thread_id: str):
    return StreamingResponse(
        sse_stream(thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

