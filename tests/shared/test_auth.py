"""shared/auth：RS256 token 验证（auth_service 的登录/签发测试在 tests/test_auth_service.py）。"""

from __future__ import annotations

from datetime import timedelta

from shared.auth.token import TokenError, decode_access_token
from shared.configs.settings import get_settings

from tests.auth_keys_helper import configure, make_token, other_private_key


def test_decode_access_token_ok(monkeypatch):
    configure(monkeypatch)
    payload = decode_access_token(make_token(sub="u1"))
    assert payload["sub"] == "u1"
    assert payload["typ"] == "access"


def test_decode_service_token_ok(monkeypatch):
    configure(monkeypatch)
    payload = decode_access_token(make_token(sub="client:dashboard", typ="service", admin=True))
    assert payload["typ"] == "service"
    assert payload["admin"] is True


def test_decode_rejects_token_signed_by_other_key(monkeypatch):
    """换一把私钥签的 token 必须被拒——这是 RS256 相对共享密钥的核心收益。"""
    configure(monkeypatch)
    forged = make_token(key=other_private_key())
    try:
        decode_access_token(forged)
    except TokenError:
        return
    raise AssertionError("expected TokenError")


def test_decode_rejects_non_allowed_type(monkeypatch):
    configure(monkeypatch)
    try:
        decode_access_token(make_token(typ="refresh"))
    except TokenError:
        return
    raise AssertionError("expected TokenError")


def test_decode_rejects_expired_token(monkeypatch):
    configure(monkeypatch)
    expired = make_token(expires_in=timedelta(seconds=-10))
    try:
        decode_access_token(expired)
    except TokenError:
        return
    raise AssertionError("expected TokenError")


def test_decode_requires_configured_public_key(monkeypatch):
    token = make_token()
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_jwt_public_key_b64", "")
    from shared.auth import token as token_module

    token_module.reset_key_cache()
    try:
        decode_access_token(token)
    except TokenError:
        return
    raise AssertionError("expected TokenError")
