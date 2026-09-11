"""测试用 RS256 密钥：生成一次，供各测试模块配置 settings 与签发 token。"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from shared.auth import token as token_module
from shared.configs.settings import get_settings

ALGORITHM = "RS256"


@lru_cache(maxsize=1)
def _keys() -> tuple[Any, str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, base64.b64encode(private_pem).decode(), base64.b64encode(public_pem).decode()


def private_key_b64() -> str:
    return _keys()[1]


def public_key_b64() -> str:
    return _keys()[2]


def configure(monkeypatch) -> None:
    """给 shared 的验签配置注入**公钥**，并清掉验签密钥缓存。

    shared 不知道私钥的存在；测试里私钥仅由本 helper 用于签发。
    """
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_jwt_public_key_b64", public_key_b64())
    token_module.reset_key_cache()


def make_token(
    *,
    sub: str = "u1",
    typ: str = "access",
    admin: bool | None = None,
    expires_in: timedelta = timedelta(hours=1),
    key: Any | None = None,
) -> str:
    """用测试私钥签一个 RS256 token（可传别的 key 模拟伪造）。"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": now,
        "exp": now + expires_in,
        "typ": typ,
    }
    if admin is not None:
        payload["admin"] = admin
    return jwt.encode(payload, key or _keys()[0], algorithm=ALGORITHM)


def other_private_key() -> Any:
    """另一把私钥，用于模拟签名不匹配。"""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)
