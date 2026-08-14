"""日志配置的单元测试：缺少 Loki 配置时也能正常初始化。"""
from shared.configs import log_config


def test_setup_logger_without_loki(monkeypatch):
    monkeypatch.setattr(log_config.settings_module, "LOKI_PUSH_URL", "")
    logger = log_config.setup_logger()
    assert logger is not None
