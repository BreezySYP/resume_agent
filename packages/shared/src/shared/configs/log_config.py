import logging
import os
import sys
from loguru import logger
from loki_logger_handler.loki_logger_handler import LokiLoggerHandler
from loki_logger_handler.formatters.loguru_formatter import LoguruFormatter
from shared.configs.settings import LOKI_PUSH_URL, APP_NAME, ENV

class InterceptHandler(logging.Handler):
    """把标准 logging 全部拦截到 loguru"""
    def emit(self, record):
        # 跳过过低的日志
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logger():
    # 创建 Loki Handler
    loki_handler = LokiLoggerHandler(
        url=LOKI_PUSH_URL,
        labels={
            "application": APP_NAME,
            "environment": ENV,
            "host": os.getenv("HOSTNAME", "localhost")
        },
        timeout=5,
        enable_self_errors=True,
        compressed=True,
        default_formatter=LoguruFormatter(),
    )

    # 配置 loguru 主处理器
    logger.configure(handlers=[
        # 控制台：显示完整日期 + 所有级别
        {
            "sink": sys.stdout,
            "level": "DEBUG",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | <level>{level:8}</level> | {message}"
        },
        # Loki：只发送 INFO 及以上
        {
            "sink": loki_handler,
            "serialize": True,
            "level": "INFO",          # ← 关键：只发送 INFO 及以上
        },
    ])

    # 拦截所有 uvicorn / fastapi 日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "uvicorn.asgi"]:
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = False
        uv_logger.addHandler(InterceptHandler())
        uv_logger.setLevel(logging.INFO)   # access log 默认是 INFO

    logger.info("✅ Logger 配置成功！已同时输出到控制台和 Loki（含 FastAPI/Uvicorn 访问日志）")
    return logger


if __name__ == "__main__":
    from shared.configs.tracing import get_tracer,span_error
    with get_tracer("test app").start_as_current_span("main test") as tracer:
        setup_logger()
        logger.trace("trace test")
        logger.debug("debug test")
        logger.warning("warning test")
        logger.exception("error test", Exception("this is an error"))
        logger.success("success test")
        logger.critical("critical test")
        logger.error("error test")
        logger.info("info test")
        span_error(tracer, Exception("span error"))
