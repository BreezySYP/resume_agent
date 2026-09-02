"""pytest 全局 fixture。"""
import os

# 测试环境禁用 LangSmith：必须在导入 shared（触发 load_dotenv）之前设置，
# 否则 .env 里的 LANGCHAIN_TRACING_V2=true 会生效，测试的 LLM 调用和
# pytest 用例都会被上传到 LangSmith。
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING", "false")
os.environ.setdefault("LANGSMITH_TRACING_V2", "false")

import pytest
from loguru import logger
from shared.configs import log_config


class _NoopLangSmithClient:
    """测试环境使用的空 client：显式 push_to_langsmith 调用变成 no-op。"""

    def create_run(self, **kwargs):
        return type("Run", (), {"id": kwargs.get("id", "noop")})()

    def update_run(self, *args, **kwargs):
        return None

    def create_feedback(self, **kwargs):
        return None


@pytest.fixture(autouse=True)
def _hermetic_logging(monkeypatch):
    """测试环境不连接 Loki，并在每个测试后清理 loguru handler。"""
    monkeypatch.setattr(log_config.settings_module, "LOKI_PUSH_URL", "")
    yield
    logger.remove()


@pytest.fixture(autouse=True)
def _hermetic_langsmith(monkeypatch):
    """测试环境不上报 LangSmith：显式推送改用空 client（测试内可自行覆盖）。"""
    from shared.rag import eval as rag_eval

    monkeypatch.setattr(rag_eval, "_ls_client", _NoopLangSmithClient())
