"""auth_service：GitHub OAuth 登录/回调、code 换 token、/me 保护。"""

from __future__ import annotations

import auth_router as router_module
from auth_config import get_auth_service_settings
from auth_keys import reset_key_cache as reset_signing_cache
from auth_router import router
from auth_tokens import create_access_token
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.auth import deps
from shared.auth.errors import add_auth_exception_handlers

from tests.auth_keys_helper import configure, private_key_b64

FAKE_USER = {
    "id": "u1",
    "email": "u1@example.com",
    "name": "u1",
    "avatar_url": None,
    "is_admin": False,
}


def _cfg(monkeypatch):
    configure(monkeypatch)  # shared 验签侧：注入测试公钥
    # 以下全部是 auth_service 私有配置（shared 不再持有这些字段）
    cfg = get_auth_service_settings()
    monkeypatch.setattr(cfg, "auth_jwt_private_key_b64", private_key_b64())
    monkeypatch.setattr(cfg, "auth_login_code_ttl", 60)
    reset_signing_cache()
    monkeypatch.setattr(cfg, "auth_session_days", 7)
    monkeypatch.setattr(cfg, "auth_frontend_origins", ["http://localhost:5173"])
    monkeypatch.setattr(cfg, "github_oauth_client_id", "client-id")
    monkeypatch.setattr(cfg, "github_oauth_client_secret", "client-secret")
    monkeypatch.setattr(cfg, "auth_redirect_uri", "http://authsvc/api/auth/callback/github")
    monkeypatch.setattr(cfg, "auth_admin_github_logins", "")
    monkeypatch.setattr(
        cfg,
        "auth_client_credentials",
        [
            {
                "client_id": "dashboard",
                "client_secret": "dashboard-secret",
                "sub": "u1",
                "admin": True,
            }
        ],
    )
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


def test_callback_github_redirects_frontend_with_one_time_code(monkeypatch):
    """回调只带一次性 code，绝不带 token。"""
    _cfg(monkeypatch)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("auth_router.redis_client", fake_redis)
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
    assert location.startswith("http://localhost:5173/app?code=")
    # URL 里不能出现 token 字样或 JWT
    assert "access_token" not in location
    assert "#" not in location
    assert shared["identity"]["provider"] == "github"
    assert shared["identity"]["account_id"] == "12345"

    # code 换 token：拿到的 JWT 才是真正的凭证
    code = location.split("code=", 1)[1]
    token_resp = _client().post(
        "/api/auth/token",
        json={"grant_type": "authorization_code", "code": code},
    )
    assert token_resp.status_code == 200
    from shared.auth.token import decode_access_token

    payload = decode_access_token(token_resp.json()["access_token"])
    assert payload["sub"] == "u1"
    assert payload["typ"] == "access"

    # code 一次性：重复使用必须失败
    replay = _client().post(
        "/api/auth/token",
        json={"grant_type": "authorization_code", "code": code},
    )
    assert replay.status_code == 400


def test_token_endpoint_rejects_unknown_code(monkeypatch):
    _cfg(monkeypatch)
    monkeypatch.setattr("auth_router.redis_client", _FakeRedis())
    resp = _client().post(
        "/api/auth/token",
        json={"grant_type": "authorization_code", "code": "not-a-real-code"},
    )
    assert resp.status_code == 400
    assert "code" in resp.json()["detail"]



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


def test_client_token_endpoint_issues_service_token(monkeypatch):
    _cfg(monkeypatch)
    resp = _client().post(
        "/api/auth/token",
        json={"client_id": "dashboard", "client_secret": "dashboard-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"

    from shared.auth.token import decode_access_token

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == "u1"
    assert payload["typ"] == "service"
    assert payload.get("admin") is True


def test_client_token_endpoint_rejects_bad_credentials(monkeypatch):
    _cfg(monkeypatch)
    resp = _client().post(
        "/api/auth/token",
        json={"client_id": "dashboard", "client_secret": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_client_token_can_request_shorter_lifetime(monkeypatch):
    import time

    _cfg(monkeypatch)
    resp = _client().post(
        "/api/auth/token",
        json={"client_id": "dashboard", "client_secret": "dashboard-secret", "days": 1},
    )
    assert resp.status_code == 200

    from shared.auth.token import decode_access_token

    payload = decode_access_token(resp.json()["access_token"])
    assert payload["exp"] - int(time.time()) <= 24 * 3600 + 60


def test_github_callback_promotes_admin(monkeypatch):
    _cfg(monkeypatch)
    cfg = get_auth_service_settings()
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


def _pat_stub(monkeypatch, *, caller_admin: bool):
    """打桩 PAT 数据访问，验证接口层的权限与返回。"""
    created: dict[str, object] = {}

    def fake_create_pat(*, user_id, name="", is_admin=False, expires_days=None):
        created.update(
            user_id=user_id, name=name, is_admin=is_admin, expires_days=expires_days
        )
        return "pat_RAWTOKEN", {
            "id": "pat-1",
            "name": name,
            "token_prefix": "pat_RAWTOK",
            "is_admin": is_admin,
        }

    monkeypatch.setattr("auth_router.create_pat", fake_create_pat)
    monkeypatch.setattr(
        "auth_router.list_pats", lambda user_id: [{"id": "pat-1", "user_id": user_id}]
    )
    monkeypatch.setattr(
        "auth_router.revoke_pat",
        lambda user_id, token_id, allow_admin=False: token_id == "pat-1",
    )
    user = {**FAKE_USER, "is_admin": caller_admin}
    return created, user


def _client_for_user(user):
    app = FastAPI()
    app.include_router(router)
    add_auth_exception_handlers(app)
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return TestClient(app, follow_redirects=False)


def test_normal_user_cannot_create_admin_token(monkeypatch):
    created, user = _pat_stub(monkeypatch, caller_admin=False)
    resp = _client_for_user(user).post(
        "/api/auth/tokens", json={"name": "script", "admin": True}
    )
    assert resp.status_code == 200
    assert created["is_admin"] is False  # 普通用户申请 admin 被服务端降级
    assert resp.json()["is_admin"] is False
    assert resp.json()["access_token"] == "pat_RAWTOKEN"


def test_admin_can_create_admin_token(monkeypatch):
    created, user = _pat_stub(monkeypatch, caller_admin=True)
    resp = _client_for_user(user).post(
        "/api/auth/tokens", json={"name": "ops", "admin": True}
    )
    assert resp.status_code == 200
    assert created["is_admin"] is True
    assert resp.json()["is_admin"] is True


def test_create_token_requires_login():
    resp = TestClient(
        _app_with_router_only(), follow_redirects=False
    ).post("/api/auth/tokens", json={"name": "x"})
    assert resp.status_code == 401


def _app_with_router_only() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    add_auth_exception_handlers(app)
    return app


def test_list_tokens_returns_items(monkeypatch):
    _, user = _pat_stub(monkeypatch, caller_admin=False)
    resp = _client_for_user(user).get("/api/auth/tokens")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "pat-1"


def test_revoke_token(monkeypatch):
    _, user = _pat_stub(monkeypatch, caller_admin=False)
    resp = _client_for_user(user).delete("/api/auth/tokens/pat-1")
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


def test_revoke_unknown_token_returns_404(monkeypatch):
    _, user = _pat_stub(monkeypatch, caller_admin=False)
    resp = _client_for_user(user).delete("/api/auth/tokens/missing")
    assert resp.status_code == 404
