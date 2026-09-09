"""conversation 路由授权依赖：owner 或 admin 可访问。"""

from __future__ import annotations

from typing import Any

from fastapi import Depends
from service.conversation_store import get_thread_owner
from shared.auth.deps import get_current_user
from shared.auth.errors import NotFoundError, PermissionDeniedError


def require_conversation_owner_or_admin(
    thread_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> None:
    """GET/DELETE 会话：admin 放行；否则必须是线程归属人，缺失/属他人按 404 处理。"""
    if user.get("is_admin"):
        return
    owner = get_thread_owner(thread_id)
    if owner is None or owner["user_id"] != user["id"]:
        raise NotFoundError(f"thread not found: {thread_id}")


def require_conversation_claim(
    thread_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> None:
    """触发 QA（登记/续写会话）：admin 放行；线程已属他人且非 admin 抛 403。"""
    if user.get("is_admin"):
        return
    owner = get_thread_owner(thread_id)
    if owner is not None and owner["user_id"] != user["id"]:
        raise PermissionDeniedError(f"thread {thread_id} 已属于其他用户")
