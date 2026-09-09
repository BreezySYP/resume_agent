"""授权依赖与领域异常映射单测（不触数据库）。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.auth.deps import require_admin, require_read_or_admin, require_self_or_admin
from shared.auth.errors import (
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    add_auth_exception_handlers,
)
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
