"""Auth Service 路由：GitHub OAuth 登录 + 签发 Bearer access token。

登录成功后 302 回前端页面，并在 URL fragment（#access_token=...）里携带
JWT；前端解析后自行保存（内存/状态管理库），后续请求通过
Authorization: Bearer 头发送。
"""

from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.parse import urlparse

from auth_github import (
    build_authorize_url,
    exchange_code,
    fetch_github_user,
    github_identity,
)
from auth_tokens import create_access_token
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from shared.auth.deps import get_current_user
from shared.auth.token import TokenError
from shared.auth.users import upsert_oauth_user
from shared.configs.settings import get_settings
from shared.db.redis import redis_client

router = APIRouter(prefix="/api/auth", tags=["Auth"])

STATE_TTL_SECONDS = 600
STATE_KEY_PREFIX = "auth:oauth:state:"
PLACEHOLDER = "xxx"


def _oauth_configured() -> str | None:
    """返回未配置原因；已配置返回 None。占位符 xxx 视为未配置。"""
    cfg = get_settings()
    client_id = (cfg.github_oauth_client_id or "").strip()
    client_secret = (cfg.github_oauth_client_secret or "").strip()
    if not client_id or client_id == PLACEHOLDER or not client_secret or client_secret == PLACEHOLDER:
        return (
            "GitHub OAuth 未配置：请在 GitHub 创建 OAuth App，"
            "并填写 GITHUB_OAUTH_CLIENT_ID / GITHUB_OAUTH_CLIENT_SECRET"
        )
    return None


def _admin_logins() -> set[str]:
    cfg = get_settings()
    return {s.strip() for s in cfg.auth_admin_github_logins.split(",") if s.strip()}


def _validate_next(next_url: str | None) -> str:
    """只允许相对路径或白名单内前端地址，防止开放重定向。

    相对路径原样返回（callback 时再拼到前端 origin 前）。
    """
    cfg = get_settings()
    allowed = {origin.rstrip("/") for origin in cfg.auth_frontend_origins}
    if not next_url:
        return "/"
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    parsed = urlparse(next_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme in {"http", "https"} and origin in allowed:
        return next_url
    return "/"


def _token_redirect_url(next_url: str, token: str) -> str:
    """把登录后的跳转目标解析成完整前端 URL，并带上 access_token fragment。"""
    cfg = get_settings()
    origins = [origin.rstrip("/") for origin in cfg.auth_frontend_origins if origin]
    base = origins[0] if origins else ""
    if next_url.startswith("/"):
        target = f"{base}{next_url}"
    else:
        target = next_url  # _validate_next 已确认在白名单内
    return f"{target}#access_token={token}"


def _save_state(state: str, next_url: str) -> None:
    redis_client.setex(
        f"{STATE_KEY_PREFIX}{state}",
        STATE_TTL_SECONDS,
        json.dumps({"next": next_url}),
    )


def _consume_state(state: str) -> str | None:
    key = f"{STATE_KEY_PREFIX}{state}"
    raw = redis_client.get(key)
    if raw is None:
        return None
    redis_client.delete(key)
    try:
        return str(json.loads(raw).get("next", "/"))
    except (TypeError, ValueError):
        return "/"


@router.get("/login/github", summary="GitHub 登录（浏览器跳转）")
async def login_github(next: str = Query("/", description="登录后跳转的相对路径")):
    unconfigured = _oauth_configured()
    if unconfigured is not None:
        raise HTTPException(status_code=503, detail=unconfigured)
    state = secrets.token_urlsafe(24)
    _save_state(state, _validate_next(next))
    return RedirectResponse(build_authorize_url(state))


@router.get("/callback/github", summary="GitHub OAuth 回调", include_in_schema=False)
async def callback_github(
    code: str = Query(""),
    state: str = Query(""),
):
    unconfigured = _oauth_configured()
    if unconfigured is not None:
        raise HTTPException(status_code=503, detail=unconfigured)
    next_url = _consume_state(state) if state else None
    if next_url is None or not code:
        raise HTTPException(status_code=400, detail="无效的 OAuth state 或缺少 code")
    try:
        access_token = await exchange_code(code)
        raw_user = await fetch_github_user(access_token)
        identity = github_identity(raw_user)
        user = upsert_oauth_user(**identity, admin_logins=_admin_logins())
    except Exception as exc:  # noqa: BLE001 - 回调统一转 502
        raise HTTPException(status_code=502, detail=f"GitHub OAuth 失败: {exc}") from exc

    try:
        token = create_access_token(user["id"])
    except TokenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RedirectResponse(_token_redirect_url(next_url or "/", token), status_code=302)


@router.get("/me", summary="当前登录用户")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user.get("email"),
        "name": user.get("name", ""),
        "avatar_url": user.get("avatar_url"),
        "is_admin": bool(user.get("is_admin")),
    }
