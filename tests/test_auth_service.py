"""auth_service：GitHub OAuth 登录/回调、fragment token 跳转、/me 保护。"""

from __future__ import annotations

import auth_router as router_module
from auth_router import router
from auth_tokens import create_access_token
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.auth import deps
from shared.auth.errors import add_auth_exception_handlers
from shared.configs.settings import get_settings

FAKE_USER = {
    "id": "u1",
    "email": "u1@example.com",
    "name": "u1",
    "avatar_url": None,
    "is_admin": False,
}


def _cfg(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_session_secret", "test-secret-" * 4)
    monkeypatch.setattr(cfg, "auth_session_days", 7)
    monkeypatch.setattr(cfg, "auth_frontend_origins", ["http://localhost:5173"])
    monkeypatch.setattr(cfg, "github_oauth_client_id", "client-id")
    monkeypatch.setattr(cfg, "github_oauth_client_secret", "client-secret")
    monkeypatch.setattr(cfg, "auth_redirect_uri", "http://authsvc/api/auth/callback/github")
    monkeypatch.setattr(cfg, "auth_admin_github_logins", "")
    return cfg


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    def setex(self, key: str, ttl: int, value: str):
        self._store[key] = value

    def get(self, key: str):
        return self._store.get(key)

    def delete(self, key: str):
        self._store.pop(key, None)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    add_auth_exception_handlers(app)
    return TestClient(app, follow_redirects=False)


def test_create_access_token_roundtrip(monkeypatch):
    _cfg(monkeypatch)
    from shared.auth.token import decode_access_token

    token = create_access_token("u1")
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["typ"] == "access"


def test_login_github_redirects_with_state(monkeypatch):
    _cfg(monkeypatch)
    saved: dict[str, str] = {}
    monkeypatch.setattr(
        "auth_router._save_state",
        lambda state, next_url: saved.update(state=state, next_url=next_url),
    )
    resp = _client().get("/api/auth/login/github?next=/app")
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=client-id" in location
    assert "state=" + saved["state"] in location
    assert saved["next_url"] == "/app"


def test_login_github_rejects_open_redirect(monkeypatch):
    _cfg(monkeypatch)
    saved: dict[str, str] = {}
    monkeypatch.setattr(
        "auth_router._save_state",
        lambda state, next_url: saved.update(state=state, next_url=next_url),
    )
    _client().get("/api/auth/login/github?next=https%3A%2F%2Fevil.example%2F")
    assert saved["next_url"] == "/"


def test_login_github_accepts_allowlisted_frontend_absolute_url(monkeypatch):
    _cfg(monkeypatch)
    saved: dict[str, str] = {}
    monkeypatch.setattr(
        "auth_router._save_state",
        lambda state, next_url: saved.update(state=state, next_url=next_url),
    )
    _client().get("/api/auth/login/github?next=http%3A%2F%2Flocalhost%3A5173%2Fdashboard")
    assert saved["next_url"] == "http://localhost:5173/dashboard"


def test_login_github_rejects_non_allowlisted_frontend_absolute_url(monkeypatch):
    _cfg(monkeypatch)
    saved: dict[str, str] = {}
    monkeypatch.setattr(
        "auth_router._save_state",
        lambda state, next_url: saved.update(state=state, next_url=next_url),
    )
    _client().get("/api/auth/login/github?next=http%3A%2F%2Fevil.example%2Fdashboard")
    assert saved["next_url"] == "/"


def test_login_github_rejects_placeholder_credentials(monkeypatch):
    cfg = _cfg(monkeypatch)
    monkeypatch.setattr(cfg, "github_oauth_client_id", "xxx")
    monkeypatch.setattr(cfg, "github_oauth_client_secret", "xxx")
    resp = _client().get("/api/auth/login/github")
    assert resp.status_code == 503
    assert "OAuth App" in resp.json()["detail"]


def test_callback_github_redirects_frontend_with_access_token(monkeypatch):
    _cfg(monkeypatch)
    monkeypatch.setattr("auth_router.redis_client", _FakeRedis())
    shared: dict[str, object] = {}

    async def fake_exchange(code: str) -> str:
        shared["code"] = code
        return "access-token"

    async def fake_fetch(token: str) -> dict:
        shared["token"] = token
        return {
            "id": 12345,
            "login": "octo",
            "email": "octo@example.com",
            "name": "Octo",
            "avatar_url": "https://avatar/1",
        }

    def fake_upsert(**kwargs) -> dict:
        shared["identity"] = kwargs
        return dict(FAKE_USER)

    monkeypatch.setattr("auth_router.exchange_code", fake_exchange)
    monkeypatch.setattr("auth_router.fetch_github_user", fake_fetch)
    monkeypatch.setattr("auth_router.upsert_oauth_user", fake_upsert)

    router_module._save_state("state-1", "/app")
    resp = _client().get("/api/auth/callback/github?code=code-1&state=state-1")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("http://localhost:5173/app#access_token=")
    assert shared["identity"]["provider"] == "github"
    assert shared["identity"]["account_id"] == "12345"


def test_me_requires_login():
    resp = _client().get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_bearer_token(monkeypatch):
    _cfg(monkeypatch)
    token = create_access_token(FAKE_USER["id"])
    monkeypatch.setattr(deps, "get_user", lambda user_id: FAKE_USER)
    resp = _client().get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "u1"
    assert resp.json()["is_admin"] is False


def test_github_callback_promotes_admin(monkeypatch):
    _cfg(monkeypatch)
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_admin_github_logins", "octo")
    monkeypatch.setattr("auth_router.redis_client", _FakeRedis())
    shared: dict[str, object] = {}

    async def fake_exchange(code: str) -> str:
        return "token"

    async def fake_fetch(token: str) -> dict:
        return {"id": 9, "login": "octo", "email": None, "name": None, "avatar_url": None}

    def fake_upsert(**kwargs) -> dict:
        shared["admin_logins"] = kwargs.get("admin_logins")
        return {**FAKE_USER, "is_admin": True}

    monkeypatch.setattr("auth_router.exchange_code", fake_exchange)
    monkeypatch.setattr("auth_router.fetch_github_user", fake_fetch)
    monkeypatch.setattr("auth_router.upsert_oauth_user", fake_upsert)
    monkeypatch.setattr("auth_router._consume_state", lambda state: "/")
    _client().get("/api/auth/callback/github?code=c&state=s")
    assert shared["admin_logins"] == {"octo"}
