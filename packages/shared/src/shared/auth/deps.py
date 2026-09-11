"""FastAPI 鉴权依赖：401 认证（Bearer token）+ 403 授权（路由依赖形态）。"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth.context import set_current_user
from shared.auth.errors import PermissionDeniedError, UnauthorizedError
from shared.auth.pats import PAT_PREFIX, verify_pat
from shared.auth.token import TokenError, decode_access_token
from shared.auth.users import get_user

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """从 Authorization: Bearer 解析 JWT、加载用户并写入 contextvar。

    依赖 `bearer_scheme` 让 FastAPI 自动在 OpenAPI 中声明 HTTPBearer，
    Swagger 页面因此会出现 Authorize 按钮。
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("未登录：请在 Authorization 头携带 Bearer token")
    raw_token = credentials.credentials

    if raw_token.startswith(PAT_PREFIX):
        pat = verify_pat(raw_token)
        if pat is None:
            raise UnauthorizedError("API key 无效、已撤销或已过期")
        user = get_user(str(pat["user_id"]))
        if user is None:
            raise UnauthorizedError("用户不存在或已注销")
        # 权限以 token 记录为准（创建时固化）；用户姓名/邮箱取实时资料
        user["is_admin"] = bool(pat["is_admin"])
        set_current_user(user)
        return user

    try:
        payload = decode_access_token(raw_token)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    if payload.get("typ") == "service":
        # service token：客户端凭证换取的 JWT，sub 即声明的身份，不再查 users 表
        service_user = {
            "id": str(payload["sub"]),
            "email": None,
            "name": "service",
            "avatar_url": None,
            "is_admin": bool(payload.get("admin", False)),
        }
        set_current_user(service_user)
        return service_user

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
