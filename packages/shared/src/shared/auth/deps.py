"""FastAPI 鉴权依赖：401 认证（Bearer token）+ 403 授权（路由依赖形态）。"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from shared.auth.context import set_current_user
from shared.auth.errors import PermissionDeniedError, UnauthorizedError
from shared.auth.token import TokenError, decode_access_token
from shared.auth.users import get_user
from shared.configs.settings import get_settings


async def get_current_user(request: Request) -> dict[str, Any]:
    """从 Authorization: Bearer 解析 JWT、加载用户并写入 contextvar。"""
    cfg = get_settings()
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("未登录：请在 Authorization 头携带 Bearer token")
    if not cfg.auth_session_secret:
        raise HTTPException(status_code=503, detail="AUTH_SESSION_SECRET 未配置")
    try:
        payload = decode_access_token(token.strip())
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = get_user(str(payload["sub"]))
    if user is None:
        raise UnauthorizedError("用户不存在或已注销")
    set_current_user(user)
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """管理端路由依赖：非管理员抛 403。"""
    if not user.get("is_admin"):
        raise PermissionDeniedError("需要管理员权限")
    return user


def require_self_or_admin(
    user_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> None:
    """资源归属为 user_id 的接口：本人或管理员可访问。"""
    if user.get("is_admin"):
        return
    if str(user_id) != str(user["id"]):
        raise PermissionDeniedError("只能访问自己的数据")


def require_read_or_admin(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> None:
    """读写分离路由依赖：GET/HEAD/OPTIONS 登录即可，其余方法需 admin。"""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not user.get("is_admin"):
        raise PermissionDeniedError("写/改操作需要管理员权限")
