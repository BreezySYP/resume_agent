"""JWT access token 验证模块（仅验证；签发在 auth_service/tokens.py）。"""

from __future__ import annotations

from typing import Any

import jwt

from shared.configs.settings import get_settings


class TokenError(Exception):
    """token 无效或服务端未配置 AUTH_SESSION_SECRET。"""


def decode_access_token(token: str) -> dict[str, Any]:
    """验证 JWT 签名与过期，返回 payload（各 API 服务调用）。"""
    cfg = get_settings()
    if not cfg.auth_session_secret:
        raise TokenError("AUTH_SESSION_SECRET 未配置")
    try:
        payload = jwt.decode(token, cfg.auth_session_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError("无效 token") from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise TokenError("无效 token")
    return payload
