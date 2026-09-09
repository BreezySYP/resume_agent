"""当前用户 contextvar 工具（等价 Java SecurityContext，仅作工具使用）。"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from shared.auth.errors import UnauthorizedError

current_user_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "current_user",
    default=None,
)


def set_current_user(user: dict[str, Any]) -> None:
    current_user_var.set(user)


def get_current_user() -> dict[str, Any]:
    """读取当前请求用户；未设置（未认证/后台任务）时抛 401。"""
    user = current_user_var.get()
    if user is None:
        raise UnauthorizedError("未登录：请先访问 /api/auth/login/github")
    return user


def clear_current_user() -> None:
    current_user_var.set(None)
