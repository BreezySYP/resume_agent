import sys
from loguru import logger
from loki_logger_handler import LokiLoggerHandler
from loki_logger_handler.formatters import LoguruFormatter

def setup_logger():
    LOKI_URL = "http://localhost:3100/loki/api/v1/push"   # 本地调试用

    loki_handler = LokiLoggerHandler(
        url=LOKI_URL,
        labels={
            "application": "myapp",
            "environment": "debug",
            "host": "localhost"
        },



        timeout=5,
        enable_self_errors=True,      # 重要！失败时在控制台显示错误
        default_formatter=LoguruFormatter(),
        
    )

    logger.configure(handlers=[
        {"sink": sys.stdout, "level": "DEBUG", "format": "{time:HH:mm:ss} | <level>{level:8}</level> | {message}"},  # 控制台
        {"sink": loki_handler, "serialize": True},   # Loki
    ])

    logger.info("✅ Logger 配置成功！已同时输出到控制台和 Loki")
    return logger