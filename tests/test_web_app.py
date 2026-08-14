"""shared.web.create_app 的单元测试。"""
from fastapi import APIRouter
from fastapi.testclient import TestClient
from shared.web.app import create_app


def _app(**kwargs):
    router = APIRouter()

    @router.get("/ping")
    def ping():
        return {"pong": True}

    defaults = dict(
        title="Test API",
        description="test",
        version="0.0.1",
        service_name="test-api",
        routers=[router],
    )
    defaults.update(kwargs)
    return create_app(**defaults)


def test_health_and_routes():
    with TestClient(_app()) as client:
        assert client.get("/").json() == {"status": "ok", "service": "test-api"}
        assert client.get("/ping").json() == {"pong": True}


def test_metrics_endpoint_only_when_provided():
    with TestClient(_app()) as client:
        assert client.get("/metrics").status_code == 404


def test_metrics_endpoint_when_provided():
    def metrics():
        return b"metric 1", "text/plain"

    with TestClient(_app(metrics_provider=metrics)) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.text == "metric 1"
