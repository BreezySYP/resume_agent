"""shared/models/deepseek.py — DeepSeek LLM 单例"""

from functools import lru_cache

from langchain_deepseek import ChatDeepSeek

from shared.configs.settings import DEEP_SEEK_KEY


@lru_cache(maxsize=1)
def get_deepseek(model: str = "deepseek-v4-flash", temperature: float = 0.0) -> ChatDeepSeek:
    if not DEEP_SEEK_KEY:
        raise RuntimeError("DEEP_SEEK_KEY 未配置，无法使用 DeepSeek 模型")
    return ChatDeepSeek(
        model=model,
        temperature=temperature,
        api_key=DEEP_SEEK_KEY,
    )
