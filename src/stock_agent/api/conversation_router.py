"""api/conversation_router.py — 读取短期 RedisSaver 中的对话并标注角色。"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger
from service.conversation_auth import require_conversation_owner_or_admin
from shared.agents.checkpoint import get_shared_aredis_checkpointer

router = APIRouter(prefix="/api/ai", tags=["Conversation"])


def _content_of(message) -> str | None:
    """提取消息正文；空消息返回 None。"""
    if not isinstance(message, (HumanMessage, SystemMessage, AIMessage)):
        return None
    content = message.content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")]
        return "".join(parts) or None
    return str(content) if content else None


def build_conversation(state: Dict[str, Any]) -> Dict[str, Any]:
    """把 checkpoint state 的 messages 通道整理成带角色标注的扁平条目列表。"""
    items: List[Dict[str, Any]] = []
    for message in state.get("messages") or []:
        if isinstance(message, str) and message.strip():
            items.append({"role": "user", "type": "user_question", "content": message})
        elif isinstance(message, HumanMessage):
            content = _content_of(message)
            if content:
                items.append({"role": "user", "type": "user_question", "content": content})
        else:
            content = _content_of(message)
            if content:
                items.append({"role": "agent", "type": "report", "content": content})

    return {
        "items": items,
        "final_answer": state.get("final_answer"),
    }


@router.get(
    "/threads/{thread_id}/conversation",
    summary="获取短期 RedisSaver 中的对话",
    dependencies=[Depends(require_conversation_owner_or_admin)],
)
async def get_conversation(thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        cp = await get_shared_aredis_checkpointer()
        snapshot = await cp.aget_tuple(config)
    except Exception as e:
        logger.exception("checkpointer read failed (thread={}): {}", thread_id, e)
        raise HTTPException(
            status_code=503, detail="对话存储（Redis）暂不可用，请稍后重试"
        ) from e
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


@router.delete(
    "/threads/{thread_id}",
    summary="清空某个线程的 RedisSaver 对话数据",
    dependencies=[Depends(require_conversation_owner_or_admin)],
)
async def delete_conversation(thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        cp = await get_shared_aredis_checkpointer()
        snapshot = await cp.aget_tuple(config)
        if snapshot is not None:
            await cp.adelete_thread(thread_id)
    except Exception as e:
        logger.exception("delete thread failed (thread={}): {}", thread_id, e)
        raise HTTPException(
            status_code=503, detail="对话存储（Redis）暂不可用，请稍后重试"
        ) from e
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    return {"deleted": True, "thread_id": thread_id}
