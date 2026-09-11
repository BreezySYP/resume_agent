"""JWT access token 验证（RS256，只验签不签发）。

签发在 auth_service（私钥只存在于该服务）；这里只做公钥验签，
公钥通过 `AUTH_JWT_PUBLIC_KEY_B64` 配置（base64 编码的 PEM，无网络请求）。
shared 不感知私钥，因此任何接入 shared 的服务都无法伪造 token。
"""

from __future__ import annotations

import base64
from functools import lru_cache
from typing import Any

import jwt

from shared.configs.settings import get_settings

ALGORITHM = "RS256"
ALLOWED_TYPES = {"access", "service"}


class TokenError(Exception):
    """token 无效或服务端未配置验签公钥。"""


@lru_cache(maxsize=1)
def _public_key() -> bytes:
    cfg = get_settings()
    if not cfg.auth_jwt_public_key_b64:
        raise TokenError("验签公钥未配置：请设置 AUTH_JWT_PUBLIC_KEY_B64")
    return base64.b64decode(cfg.auth_jwt_public_key_b64)


def reset_key_cache() -> None:
    """清除公钥缓存（测试或更换密钥后使用）。"""
    _public_key.cache_clear()


def decode_access_token(token: str) -> dict[str, Any]:
    """验证 JWT 签名与过期，返回 payload（各 API 服务调用）。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _public_key(),
            algorithms=[ALGORITHM],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("无效 token") from exc
    if payload.get("typ") not in ALLOWED_TYPES or not payload.get("sub"):
        raise TokenError("无效 token")
    return payload
