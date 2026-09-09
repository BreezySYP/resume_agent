"""JWT access token 签发（仅 auth_service 需要；各 API 服务只做验证）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from shared.auth.token import TokenError
from shared.configs.settings import get_settings


def create_access_token(user_id: str) -> str:
    """签发短期 JWT access token。"""
    cfg = get_settings()
    if not cfg.auth_session_secret:
        raise TokenError("AUTH_SESSION_SECRET 未配置")
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=cfg.auth_session_days),
        "typ": "access",
    }
    return jwt.encode(payload, cfg.auth_session_secret, algorithm="HS256")
