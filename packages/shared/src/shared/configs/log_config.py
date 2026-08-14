"""shared/configs/log_config.py — 统一日志配置（loguru + 可选 Loki）"""

import logging
import os
import sys

from loguru import logger
from loki_logger_handler.formatters.loguru_formatter import LoguruFormatter
from loki_logger_handler.loki_logger_handler import LokiLoggerHandler

from shared.configs import settings as settings_module


class InterceptHandler(logging.Handler):
    """把标准 logging 全部拦截到 loguru"""

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logger():
    handlers = [
        {
            "sink": sys.stdout,
            "level": "DEBUG",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | <level>{level:8}</level> | {message}",
        },
    ]

    # 只有配置了 Loki 时才发送日志，避免本地开发因缺少基础设施而报错
    if settings_module.LOKI_PUSH_URL:
        loki_handler = LokiLoggerHandler(
            url=settings_module.LOKI_PUSH_URL,
            labels={
                "application": settings_module.APP_NAME,
                "environment": settings_module.ENV,
                "host": os.getenv("HOSTNAME", "localhost"),
            },
            timeout=5,
            enable_self_errors=True,
            compressed=True,
            default_formatter=LoguruFormatter(),
        )
        handlers.append(
            {
                "sink": loki_handler,
                "serialize": True,
                "level": "INFO",
            }
        )

    logger.configure(handlers=handlers)

    # 拦截所有 uvicorn / fastapi 日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "uvicorn.asgi"]:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = False
        uv_logger.addHandler(InterceptHandler())
        uv_logger.setLevel(logging.INFO)

    logger.info("✅ Logger 配置成功！已输出到控制台{}",
                " + Loki" if settings_module.LOKI_PUSH_URL else "")
    return logger
