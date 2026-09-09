"""dashboard 权限：股票只读需登录，ETL/状态接口需管理员。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import etl, stocks
from shared.auth.deps import get_current_user
from shared.auth.errors import add_auth_exception_handlers

NORMAL_USER = {
    "id": "u1",
    "email": "u1@example.com",
    "name": "u1",
    "avatar_url": None,
    "is_admin": False,
}
ADMIN_USER = {**NORMAL_USER, "id": "admin", "is_admin": True}


def _app(router, user=None):
    app = FastAPI()
    app.include_router(router)
    add_auth_exception_handlers(app)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_stocks_require_login():
    assert _app(stocks.router).get("/api/stocks").status_code == 401


def test_etl_steps_require_login():
    assert _app(etl.router).get("/api/etl/steps").status_code == 401


def test_etl_steps_forbidden_for_normal_user():
    assert _app(etl.router, NORMAL_USER).get("/api/etl/steps").status_code == 403


def test_etl_steps_allowed_for_admin():
    resp = _app(etl.router, ADMIN_USER).get("/api/etl/steps")
    assert resp.status_code == 200
