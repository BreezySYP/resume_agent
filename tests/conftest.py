"""pytest 全局 fixture。"""
import pytest
from loguru import logger
from shared.configs import log_config


@pytest.fixture(autouse=True)
def _hermetic_logging(monkeypatch):
    """测试环境不连接 Loki，并在每个测试后清理 loguru handler。"""
    monkeypatch.setattr(log_config.settings_module, "LOKI_PUSH_URL", "")
    yield
    logger.remove()
