"""shared/web/app.py — 统一 FastAPI 应用工厂"""

from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from shared.configs.log_config import setup_logger
from shared.configs.settings import CORS_ORIGINS

MetricsProvider = Callable[[], tuple[bytes, str]]


def create_app(
    *,
    title: str,
    description: str,
    version: str,
    service_name: str,
    routers: Iterable[APIRouter],
    metrics_provider: MetricsProvider | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """创建一个统一配置的 FastAPI 应用。

    所有服务共用同一套：日志初始化、CORS、健康检查，以及可选的 /metrics 端点。
    """

    # 在应用创建（模块导入）时尽早初始化日志，保证 uvicorn 自身的启动日志也走
    # loguru 统一格式，而不是先输出 uvicorn 默认格式、等 lifespan 里才切换。
    setup_logger()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("🚀 启动 {}", title)
        yield
        logger.info("👋 {} 关闭", title)

    app = FastAPI(title=title, description=description, version=version, lifespan=lifespan)

    origins = cors_origins if cors_origins is not None else CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in routers:
        app.include_router(router)

    @app.get("/", tags=["健康检查"], summary="服务健康检查")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    if metrics_provider is not None:

        @app.get("/metrics")
        def metrics() -> Response:
            body, content_type = metrics_provider()
            return Response(content=body, media_type=content_type)

    return app
