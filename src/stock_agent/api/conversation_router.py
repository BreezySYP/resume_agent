"""api/conversation_router.py — 读取短期 RedisSaver 中的对话并标注角色。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, SystemMessage
from shared.agents.checkpoint import get_aredis_checkpointer

router = APIRouter(prefix="/api/ai", tags=["Conversation"])


def _content_of(message) -> str | None:
    """提取消息正文；空消息返回 None。"""
    if not isinstance(message, (SystemMessage, AIMessage)):
        return None
    content = message.content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")]
        return "".join(parts) or None
    return str(content) if content else None


def _serialize(value) -> str:
    """dict/list 序列化成 JSON 字符串，普通字符串原样返回。"""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def build_conversation(state: Dict[str, Any]) -> Dict[str, Any]:
    """把 checkpoint state 整理成带角色标注的扁平条目列表。"""
    items: List[Dict[str, Any]] = []

    user_question = state.get("user_question")
    if not user_question:
        # 回退：messages 里第一条纯字符串（supervisor 写入的用户问题）
        for message in state.get("messages") or []:
            if isinstance(message, str) and message.strip():
                user_question = message
                break
    if user_question:
        items.append({"role": "user", "type": "user_question", "content": str(user_question)})

    plan = state.get("plan")
    if plan:
        items.append({"role": "reasoning", "type": "plan", "content": _serialize(plan)})

    news_analysis = state.get("news_analysis")
    if news_analysis:
        items.append(
            {"role": "reasoning", "type": "news_analysis", "content": str(news_analysis)}
        )

    for message in state.get("messages") or []:
        if isinstance(message, str):
            continue
        content = _content_of(message)
        if content:
            items.append({"role": "agent", "type": "report", "content": content})

    for reflection in state.get("reflections") or []:
        items.append(
            {"role": "reasoning", "type": "reflection", "content": _serialize(reflection)}
        )

    return {
        "items": items,
        "final_answer": state.get("final_answer"),
    }


@router.get("/threads/{thread_id}/conversation", summary="获取短期 RedisSaver 中的对话")
async def get_conversation(thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    async with get_aredis_checkpointer() as cp:
        snapshot = await cp.aget_tuple(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")

    state = snapshot.checkpoint["channel_values"]
    conversation = build_conversation(state)
    return {
        "thread_id": thread_id,
        "job_id": state.get("job_id"),
        "current_time": state.get("current_time"),
        **conversation,
    }
