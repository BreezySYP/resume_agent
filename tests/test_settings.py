"""shared.configs.settings 的单元测试。"""
import shared.configs.settings as settings_module
from shared.configs.settings import Settings, get_settings


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
