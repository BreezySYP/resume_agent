"""鉴权领域异常 + FastAPI 全局映射（service/依赖层不直接抛 HTTPException）。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse


class AuthError(Exception):
    status_code: int = 500
    detail: str = "鉴权失败"

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class UnauthorizedError(AuthError):
    """401：未登录 / 会话无效。"""

    status_code = 401
    detail = "未登录"


class PermissionDeniedError(AuthError):
    """403：已登录但无权访问。"""

    status_code = 403
    detail = "权限不足"


class NotFoundError(AuthError):
    """404：资源不存在（用于避免暴露他人资源存在性）。"""

    status_code = 404
    detail = "资源不存在"


async def _auth_error_handler(request: Any, exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def add_auth_exception_handlers(app: FastAPI) -> None:
    """注册领域异常 → HTTP 状态映射（create_app 与单测临时 app 共用）。"""
    for exc_type in (AuthError, UnauthorizedError, PermissionDeniedError, NotFoundError):
        app.add_exception_handler(exc_type, _auth_error_handler)
