"""shared/auth：JWT 验证（auth_service 的登录/签发测试在 tests/auth_service）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from shared.auth.token import TokenError, decode_access_token
from shared.configs.settings import get_settings

TEST_SECRET = "test-secret-" * 4


def _cfg(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_session_secret", TEST_SECRET)
    return cfg


def _encode(token_typ: str = "access", secret: str = TEST_SECRET) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "u1",
            "iat": now,
            "exp": now + timedelta(days=1),
            "typ": token_typ,
        },
        secret,
        algorithm="HS256",
    )


def test_decode_access_token_ok(monkeypatch):
    _cfg(monkeypatch)
    payload = decode_access_token(_encode())
    assert payload["sub"] == "u1"
    assert payload["typ"] == "access"


def test_decode_access_token_rejects_wrong_secret(monkeypatch):
    _cfg(monkeypatch)
    try:
        decode_access_token(_encode(secret="another-secret-" * 4))
    except TokenError:
        return
    raise AssertionError("expected TokenError")


def test_decode_access_token_rejects_non_access_type(monkeypatch):
    _cfg(monkeypatch)
    try:
        decode_access_token(_encode(token_typ="refresh"))
    except TokenError:
        return
    raise AssertionError("expected TokenError")


def test_decode_access_token_requires_secret(monkeypatch):
    token = _encode()
    _cfg(monkeypatch)  # 先恢复有效 secret 语境
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_session_secret", "")  # 再清空模拟未配置
    try:
        decode_access_token(token)
    except TokenError:
        return
    raise AssertionError("expected TokenError")
