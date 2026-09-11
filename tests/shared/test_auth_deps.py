"""授权依赖与领域异常映射单测（不触数据库）。"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from shared.auth.deps import (
    get_current_user,
    require_admin,
    require_read_or_admin,
    require_self_or_admin,
)
from shared.auth.errors import (
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    add_auth_exception_handlers,
)
from shared.configs.settings import get_settings
from starlette.requests import Request

NORMAL_USER = {
    "id": "u1",
    "email": "u1@example.com",
    "name": "u1",
    "avatar_url": None,
    "is_admin": False,
}
ADMIN_USER = {**NORMAL_USER, "id": "admin", "is_admin": True}


def _request(method: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/stocks",
            "raw_path": b"/api/stocks",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "http_version": "1.1",
            "root_path": "",
        }
    )


def test_require_self_or_admin_allows_owner() -> None:
    require_self_or_admin("u1", NORMAL_USER)


def test_require_self_or_admin_rejects_other_user() -> None:
    with pytest.raises(PermissionDeniedError):
        require_self_or_admin("u2", NORMAL_USER)


def test_require_self_or_admin_allows_admin() -> None:
    require_self_or_admin("u2", ADMIN_USER)


def test_require_admin_allows_admin() -> None:
    require_admin(ADMIN_USER)


def test_require_admin_rejects_normal_user() -> None:
    with pytest.raises(PermissionDeniedError):
        require_admin(NORMAL_USER)


def test_require_read_or_admin_allows_get_for_normal_user() -> None:
    require_read_or_admin(_request("GET"), NORMAL_USER)


def test_require_read_or_admin_rejects_post_for_normal_user() -> None:
    with pytest.raises(PermissionDeniedError):
        require_read_or_admin(_request("POST"), NORMAL_USER)


def test_require_read_or_admin_allows_post_for_admin() -> None:
    require_read_or_admin(_request("POST"), ADMIN_USER)


def test_domain_errors_map_to_http_status() -> None:
    app = FastAPI()
    add_auth_exception_handlers(app)

    @app.get("/e401")
    def _e401():
        raise UnauthorizedError("未登录")

    @app.get("/e403")
    def _e403():
        raise PermissionDeniedError("需要管理员权限")

    @app.get("/e404")
    def _e404():
        raise NotFoundError("thread not found")

    client = TestClient(app)
    assert client.get("/e401").status_code == 401
    assert client.get("/e403").status_code == 403
    assert client.get("/e404").status_code == 404


def test_openapi_declares_bearer_security_for_swagger() -> None:
    """受保护路由通过 HTTPBearer 依赖自动声明 security，Swagger 出现 Authorize 按钮。"""
    app = FastAPI()
    add_auth_exception_handlers(app)

    @app.get("/protected")
    def _protected(user: dict = Depends(get_current_user)):
        return user

    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/protected"]["get"]["security"] == [{"HTTPBearer": []}]


def test_service_token_bypasses_users_table(monkeypatch) -> None:
    """typ=service 的 JWT 按声明授权，不查 users 表。"""
    from tests.auth_keys_helper import configure, make_token

    configure(monkeypatch)
    token = make_token(sub="client:dashboard", typ="service", admin=True)

    app = FastAPI()
    add_auth_exception_handlers(app)

    @app.get("/protected")
    def _protected(user: dict = Depends(get_current_user)):
        return user

    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "client:dashboard"
    assert resp.json()["is_admin"] is True


def test_pat_token_authenticates_without_jwt_secret(monkeypatch) -> None:
    """Bearer pat_xxx 走 PAT 查库路径，不需要任何 JWT 密钥配置。"""
    from shared.auth import deps as deps_module
    from shared.auth import token as token_module

    monkeypatch.setattr(
        deps_module, "verify_pat", lambda token: {"user_id": "u1", "is_admin": True}
    )
    monkeypatch.setattr(
        deps_module,
        "get_user",
        lambda user_id: {
            "id": user_id,
            "email": "u1@example.com",
            "name": "u1",
            "avatar_url": None,
            "is_admin": False,
        },
    )
    # 故意不配置任何 JWT 密钥，证明 PAT 路径不依赖 JWT
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_jwt_public_key_b64", "")
    token_module.reset_key_cache()

    app = FastAPI()
    add_auth_exception_handlers(app)

    @app.get("/protected")
    def _protected(user: dict = Depends(get_current_user)):
        return user

    resp = TestClient(app).get(
        "/protected", headers={"Authorization": "Bearer pat_some_opaque_key"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "u1"
    assert resp.json()["is_admin"] is True  # 采用 token 记录固化的权限


def test_pat_token_rejected_when_invalid(monkeypatch) -> None:
    from shared.auth import deps as deps_module

    monkeypatch.setattr(deps_module, "verify_pat", lambda token: None)

    app = FastAPI()
    add_auth_exception_handlers(app)

    @app.get("/protected")
    def _protected(user: dict = Depends(get_current_user)):
        return user

    resp = TestClient(app).get(
        "/protected", headers={"Authorization": "Bearer pat_revoked"}
    )
    assert resp.status_code == 401
