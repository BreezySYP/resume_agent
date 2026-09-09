"""api/agent_router.py — AI Agent 触发与 SSE 订阅"""
from agent.graph import ask_investment
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from service.conversation_auth import require_conversation_claim
from service.conversation_store import claim_thread
from shared.auth import context as auth_context
from shared.auth.deps import get_current_user
from shared.auth.errors import PermissionDeniedError
from shared.db.redis import sse_stream

router = APIRouter(prefix="/api/ai", tags=["AI tasks"])


class TriggerAgentRequest(BaseModel):
    thread_id: str = Field(..., description="会话 ID")
    job_id: str = Field(..., description="任务 ID")
    question: str = Field(..., description="用户问题")


class TriggerAgentResponse(BaseModel):
    thread_id: str
    message: str


@router.post(
    "/qa",
    response_model=TriggerAgentResponse,
    summary="触发 AI Agent 回答问题",
    dependencies=[Depends(require_conversation_claim)],
)
async def trigger_agent(qa: TriggerAgentRequest, background: BackgroundTasks):
    user = auth_context.get_current_user()
    try:
        claim_thread(qa.thread_id, user["id"])
    except PermissionError as exc:
        raise PermissionDeniedError(str(exc)) from exc
    background.add_task(
        ask_investment,
        qa.question,
        qa.job_id,
        qa.thread_id,
        user_id=user["id"],
    )
    return TriggerAgentResponse(
        thread_id=qa.thread_id,
        message="ai stock agent is triggered for the question",
    )


@router.get(
    "/qa/stream/{job_id}",
    summary="订阅 AI Agent 的回答进度（SSE）",
    dependencies=[Depends(get_current_user)],
)
async def stream_agent(job_id: str):
    return StreamingResponse(
        sse_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
