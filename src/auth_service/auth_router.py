"""Auth Service 路由：GitHub OAuth 登录 + 签发 Bearer access token。

登录成功后 302 回前端并带**一次性 code**（不是 token）；
前端用 code 调 `POST /api/auth/token`（grant_type=authorization_code）换取 JWT，
所以 token 不会出现在 URL、历史记录或服务端日志里。

同一个 token 端点也支持 client credentials（grant_type=client_credentials），
供无用户归属的后台任务/内部服务换取 service token。
"""

from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.parse import quote, urlparse

from auth_config import get_auth_service_settings
from auth_github import (
    build_authorize_url,
    exchange_code,
    fetch_github_user,
    github_identity,
)
from auth_tokens import create_access_token, create_service_token
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pats import create_pat, list_pats, revoke_pat
from pydantic import BaseModel, Field
from shared.auth.deps import get_current_user
from shared.auth.token import TokenError
from shared.auth.users import upsert_oauth_user
from shared.db.redis import redis_client

router = APIRouter(prefix="/api/auth", tags=["Auth"])

STATE_TTL_SECONDS = 600
STATE_KEY_PREFIX = "auth:oauth:state:"
LOGIN_CODE_KEY_PREFIX = "auth:login:code:"
PLACEHOLDER = "xxx"


class ClientTokenRequest(BaseModel):
    """换取 token 的请求（OAuth2 token 端点风格）。

    - `grant_type=authorization_code`：用浏览器登录拿到的一次性 code 换用户 JWT；
    - `grant_type=client_credentials`：用 client_id/client_secret 换 service JWT。

    不传 grant_type 时按字段推断（有 code 视为 authorization_code）。
    """

    grant_type: str | None = Field(default=None, description="authorization_code / client_credentials")
    code: str | None = Field(default=None, description="authorization_code 流程：一次性登录 code")
    client_id: str | None = Field(default=None, description="客户端 ID（AUTH_CLIENT_CREDENTIALS 中配置）")
    client_secret: str | None = Field(default=None, description="客户端密钥")
    days: int | None = Field(default=None, ge=1, le=30, description="有效期天数，默认 AUTH_SESSION_DAYS")
    admin: bool = Field(default=False, description="是否签发管理员 service token")


class CreateTokenRequest(BaseModel):
    """用户自助创建 personal access token（API key）。"""

    name: str = Field(default="", max_length=255, description="备注名，如「我的脚本」")
    expires_days: int | None = Field(default=None, ge=1, le=365, description="有效期天数，不填则不过期")
    admin: bool = Field(default=False, description="申请管理员权限（仅管理员生效，普通用户会被降级）")


def _oauth_configured() -> str | None:
    """返回未配置原因；已配置返回 None。占位符 xxx 视为未配置。"""
    cfg = get_auth_service_settings()
    client_id = (cfg.github_oauth_client_id or "").strip()
    client_secret = (cfg.github_oauth_client_secret or "").strip()
    if not client_id or client_id == PLACEHOLDER or not client_secret or client_secret == PLACEHOLDER:
        return (
            "GitHub OAuth 未配置：请在 GitHub 创建 OAuth App，"
            "并填写 GITHUB_OAUTH_CLIENT_ID / GITHUB_OAUTH_CLIENT_SECRET"
        )
    return None


def _find_client(client_id: str, client_secret: str) -> dict[str, Any] | None:
    cfg = get_auth_service_settings()
    for client in cfg.auth_client_credentials:
        if (
            client.get("client_id") == client_id
            and client.get("client_secret") == client_secret
        ):
            return client
    return None


def _admin_logins() -> set[str]:
    cfg = get_auth_service_settings()
    return {s.strip() for s in cfg.auth_admin_github_logins.split(",") if s.strip()}


def _validate_next(next_url: str | None) -> str:
    """只允许相对路径或白名单内前端地址，防止开放重定向。

    相对路径原样返回（callback 时再拼到前端 origin 前）。
    """
    cfg = get_auth_service_settings()
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


def _code_redirect_url(next_url: str, code: str) -> str:
    """把登录后的跳转目标解析成完整前端 URL，并带上一次性 code（不是 token）。"""
    cfg = get_auth_service_settings()
    origins = [origin.rstrip("/") for origin in cfg.auth_frontend_origins if origin]
    base = origins[0] if origins else ""
    if next_url.startswith("/"):
        target = f"{base}{next_url}"
    else:
        target = next_url  # _validate_next 已确认在白名单内
    # code 放在 query：它是一次性、短时效的，泄漏后也无法单独使用
    separator = "&" if "?" in target else "?"
    return f"{target}{separator}code={quote(code, safe='')}"


def _save_login_code(code: str, user_id: str) -> None:
    """登录 code 存 Redis，短 TTL，兑换时一次性消费。"""
    redis_client.setex(
        f"{LOGIN_CODE_KEY_PREFIX}{code}",
        get_auth_service_settings().auth_login_code_ttl,
        json.dumps({"user_id": user_id}),
    )


def _consume_login_code(code: str) -> str | None:
    key = f"{LOGIN_CODE_KEY_PREFIX}{code}"
    raw = redis_client.get(key)
    if raw is None:
        return None
    redis_client.delete(key)
    try:
        return str(json.loads(raw)["user_id"])
    except (TypeError, ValueError, KeyError):
        return None


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

    login_code = secrets.token_urlsafe(32)
    _save_login_code(login_code, str(user["id"]))
    return RedirectResponse(_code_redirect_url(next_url or "/", login_code), status_code=302)


@router.post(
    "/token",
    summary="换取 token（authorization_code 用户登录 / client_credentials 服务凭证）",
    response_model=dict[str, Any],
)
def issue_token(payload: ClientTokenRequest) -> dict[str, Any]:
    """OAuth2 token 端点：把一次性 code 换成 JWT，或用 client credentials 换 service token。"""
    cfg = get_auth_service_settings()
    grant_type = payload.grant_type
    if grant_type is None:
        grant_type = "authorization_code" if payload.code else "client_credentials"

    if grant_type == "authorization_code":
        if not payload.code:
            raise HTTPException(status_code=400, detail="缺少 code")
        user_id = _consume_login_code(payload.code)
        if user_id is None:
            raise HTTPException(status_code=400, detail="code 无效或已过期，请重新登录")
        try:
            token = create_access_token(user_id)
        except TokenError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": cfg.auth_session_days * 24 * 3600,
        }

    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail=f"不支持的 grant_type: {grant_type}")
    if not payload.client_id or not payload.client_secret:
        raise HTTPException(status_code=400, detail="缺少 client_id / client_secret")
    client = _find_client(payload.client_id, payload.client_secret)
    if client is None:
        raise HTTPException(status_code=401, detail="无效的 client_id / client_secret")
    sub = str(client.get("sub") or client["client_id"])
    try:
        token = create_service_token(
            sub=sub,
            admin=bool(client.get("admin", False) or payload.admin),
            days=payload.days,
        )
    except TokenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": (payload.days or cfg.auth_session_days) * 24 * 3600,
    }


@router.post(
    "/tokens",
    summary="创建 personal access token（API key），明文仅返回一次",
    response_model=dict[str, Any],
)
def create_personal_token(
    payload: CreateTokenRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """UI 调用入口：登录用户生成自己的 API key。

    权限上限由服务端强制：非管理员即使传 admin=true 也只能得到普通 token。
    """
    # 服务端强制上限：只有本身是管理员的用户才能拿到 admin token
    granted_admin = bool(user.get("is_admin")) if payload.admin else False
    raw, info = create_pat(
        user_id=str(user["id"]),
        name=payload.name,
        is_admin=granted_admin,
        expires_days=payload.expires_days,
    )
    return {
        "access_token": raw,
        "token_type": "bearer",
        "token": info,
        "is_admin": granted_admin,
        "notice": "请立即保存，明文只显示这一次；之后只能看到前缀。",
    }


@router.get(
    "/tokens",
    summary="列出当前用户的 personal access token（不含明文）",
    response_model=dict[str, Any],
)
def list_personal_tokens(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"items": list_pats(str(user["id"]))}


@router.delete(
    "/tokens/{token_id}",
    summary="撤销 personal access token",
    response_model=dict[str, Any],
)
def revoke_personal_token(
    token_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    ok = revoke_pat(str(user["id"]), token_id, allow_admin=bool(user.get("is_admin")))
    if not ok:
        raise HTTPException(status_code=404, detail="token 不存在或无权操作")
    return {"revoked": True, "id": token_id}


@router.get("/me", summary="当前登录用户")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user.get("email"),
        "name": user.get("name", ""),
        "avatar_url": user.get("avatar_url"),
        "is_admin": bool(user.get("is_admin")),
    }
