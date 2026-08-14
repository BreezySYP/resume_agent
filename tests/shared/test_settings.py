"""shared.configs.settings 的单元测试。"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import shared.configs.settings as settings_module
from dotenv import dotenv_values
from shared.configs.settings import Settings, get_settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_defaults_are_available():
    s = get_settings()
    assert s.redis_url.startswith("redis://")
    assert isinstance(s.mysql_port, int)
    assert s.graph_config["configurable"]["thread_id"]


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://test-host:9999")
    monkeypatch.setenv("MYSQL_ROOT_PASSWORD", "secret")
    monkeypatch.setenv("NAME", "test-service")
    s = Settings()
    assert s.redis_url == "redis://test-host:9999"
    assert s.mysql_password == "secret"
    assert s.app_name == "test-service"


def test_module_level_names_are_exported():
    assert settings_module.REDIS_URL.startswith("redis://")
    assert isinstance(settings_module.MYSQL_PORT, int)
    assert settings_module.GRAPH_CONFIG["configurable"]["thread_id"]


def _settings_env_names() -> dict[str, str]:
    """Settings 每个字段对应的环境变量名（字段名大写或 validation_alias）。"""
    return {
        field_name: str(field.validation_alias) if field.validation_alias else field_name.upper()
        for field_name, field in Settings.model_fields.items()
    }


def _env_keys(filename: str) -> set[str]:
    values = dotenv_values(_PROJECT_ROOT / filename)
    return {key.lower() for key in values if key}


def test_env_example_covers_all_settings_fields():
    """settings 每个字段都必须在 .env.example 中有对应配置项（同步契约）。"""
    example_keys = _env_keys(".env.example")
    missing = [env for env in _settings_env_names().values() if env.lower() not in example_keys]
    assert not missing, f".env.example 缺少 settings 字段对应配置: {missing}"


@pytest.mark.skipif(not (_PROJECT_ROOT / ".env").exists(), reason="本地 .env 不存在")
def test_env_file_covers_all_settings_fields():
    """本地 .env 必须覆盖 settings 的所有字段。"""
    env_keys = _env_keys(".env")
    missing = [env for env in _settings_env_names().values() if env.lower() not in env_keys]
    assert not missing, f".env 缺少 settings 字段对应配置: {missing}"


@pytest.mark.skipif(not (_PROJECT_ROOT / ".env.prod").exists(), reason="本地 .env.prod 不存在")
def test_env_prod_covers_all_settings_fields():
    """本地 .env.prod 必须覆盖 settings 的所有字段。"""
    prod_keys = _env_keys(".env.prod")
    missing = [env for env in _settings_env_names().values() if env.lower() not in prod_keys]
    assert not missing, f".env.prod 缺少 settings 字段对应配置: {missing}"


def test_env_example_has_no_real_secrets():
    """.env.example 中的敏感键只能放占位符，不能出现真实密钥。"""
    sensitive_hints = ("API_KEY", "TOKEN", "PASSWORD", "SECRET")
    suspicious = []
    for key, value in dotenv_values(_PROJECT_ROOT / ".env.example").items():
        upper_key = key.upper()
        if not value or not any(hint in upper_key for hint in sensitive_hints):
            continue
        stripped = value.strip()
        looks_like_key = bool(re.match(r"^sk-[A-Za-z0-9_-]{16,}$", stripped))
        long_value = len(stripped) >= 24 and not stripped.lower().startswith("sk-xxxx")
        if looks_like_key or long_value:
            suspicious.append((key, len(stripped)))
    assert not suspicious, f".env.example 疑似包含真实密钥: {suspicious}"


@pytest.mark.skipif(not (_PROJECT_ROOT / ".env").exists(), reason="本地 .env 不存在")
def test_real_env_overrides_dotenv_file():
    """容器部署契约：真实环境变量优先于 .env 文件（即使镜像内存在 .env）。"""
    code = (
        "from shared.configs.settings import _settings as s; "
        "print(s.ollama_url); print(s.thread_id)"
    )
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env["PYTHONPATH"] = os.environ.get(
        "PYTHONPATH",
        str(_PROJECT_ROOT / "packages/shared/src") + os.pathsep + str(_PROJECT_ROOT / "src/stock_agent"),
    )
    env["OLLAMA_URL"] = "http://env-var-test:9999"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "http://env-var-test:9999", "环境变量应优先于 .env"
    assert lines[1] != "agent_001", ".env 应补足未通过环境变量设置的配置"
