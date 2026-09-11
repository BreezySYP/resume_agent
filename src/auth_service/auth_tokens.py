"""JWT access token 签发（RS256，私钥只在本服务；各 API 服务只用公钥验证）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from auth_config import get_auth_service_settings
from auth_keys import sign


def create_access_token(user_id: str) -> str:
    """签发用户 access token（RS256）。"""
    cfg = get_auth_service_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=cfg.auth_session_days),
        "typ": "access",
    }
    return sign(payload)


def create_service_token(
    *,
    sub: str,
    admin: bool = False,
    days: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """签发 service token（client credentials 换取的 JWT，typ=service，RS256）。"""
    cfg = get_auth_service_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(days=days if days is not None else cfg.auth_session_days),
        "typ": "service",
    }
    if admin:
        payload["admin"] = True
    if extra:
        payload.update(extra)
    return sign(payload)
