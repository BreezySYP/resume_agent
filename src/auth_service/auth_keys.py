"""JWT 签名私钥（RS256）：只在本服务存在，并对外提供派生公钥。

- 私钥来自 `AUTH_JWT_PRIVATE_KEY_B64`（base64 编码的 PEM），配置定义在
  本服务的 `auth_config.py`，不存在于 shared；
- 其他服务用 `AUTH_JWT_PUBLIC_KEY_B64`（由这里派生）离线验签，拿不到签发能力；
- 本服务自己也只通过公钥验签：启动时把派生公钥写回 shared 的验签配置。
"""

from __future__ import annotations

import base64
from functools import lru_cache
from typing import Any

import jwt
from auth_config import get_auth_service_settings
from cryptography.hazmat.primitives import serialization
from shared.auth.token import ALGORITHM, TokenError, reset_key_cache
from shared.configs.settings import get_settings


@lru_cache(maxsize=1)
def private_key() -> Any:
    cfg = get_auth_service_settings()
    if not cfg.auth_jwt_private_key_b64:
        raise TokenError(
            "AUTH_JWT_PRIVATE_KEY_B64 未配置：生成方式 "
            "openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 | base64 -w0"
        )
    return serialization.load_pem_private_key(
        base64.b64decode(cfg.auth_jwt_private_key_b64), password=None
    )


def public_key_b64() -> str:
    """派生公钥（base64 PEM）：给其他服务配 AUTH_JWT_PUBLIC_KEY_B64，也用于本地验签。"""
    return base64.b64encode(
        private_key().public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode()


def sign(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, private_key(), algorithm=ALGORITHM)


def configure_shared_verification() -> None:
    """把公钥交给 shared 的验签配置（只给公钥，不给私钥）。"""
    get_settings().auth_jwt_public_key_b64 = public_key_b64()
    reset_key_cache()


def reset_signing_cache() -> None:
    """清除私钥缓存（测试或更换密钥后使用）。"""
    private_key.cache_clear()
