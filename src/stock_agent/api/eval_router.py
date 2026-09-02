"""api/eval_router.py — 纯 faithfulness 检查 REST API（answer / question / rag_context）。"""

from __future__ import annotations

from typing import Any, List

from eval.faithfulness import caculate_faithfulness_score
from eval.feedback import build_faithfulness_claims
from fastapi import APIRouter, HTTPException
from loguru import logger
from observe.metrics import record_eval_scores, track_eval_run
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai", tags=["Eval"])


class FaithfulnessRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="Agent 最终回答")
    question: str = Field(..., min_length=1, description="用户问题")
    rag_context: List[Any] = Field(
        default_factory=list,
        description=(
            "RAG 记录列表：每条可带 source 字段（profile/financial/technical/news/memory）"
            "或按字段自动识别"
        ),
    )


@router.post("/faithfulness", summary="faithfulness 检查：只跑 claim 拆解 + 证据判定")
async def faithfulness_check(req: FaithfulnessRequest) -> dict:
    try:
        with track_eval_run():
            score, results = await caculate_faithfulness_score(
                req.answer,
                req.question,
                req.rag_context,
            )
        record_eval_scores({"faithfulness": score})
        return {
            "faithfulness": score,
            "faithfulness_claims": build_faithfulness_claims(results),
        }
    except Exception as e:
        logger.exception("faithfulness check failed: {}", e)
        raise HTTPException(status_code=500, detail=f"faithfulness check failed: {e}") from e
