"""shared/db/redis_cache.py — Redis DataFrame 缓存装饰器"""
import functools
import hashlib
import io

import pandas as pd
from loguru import logger
from redis import Redis
from shared.configs.settings import REDIS_URL

r = Redis.from_url(REDIS_URL)


def _default_key(func, *args, **kwargs) -> str:
    content = (func.__module__, func.__name__, args, tuple(sorted(kwargs.items())))
    digest = hashlib.sha256(repr(content).encode()).hexdigest()[:16]
    return f"cache:df:{func.__name__}:{digest}"


def redis_cache_df_parquet(expire_seconds: int = 172800, key_generator=_default_key):
    """装饰器：将 DataFrame 结果缓存到 Redis（Parquet 格式）"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = key_generator(func, *args, **kwargs)
            cached = r.get(key)
            if cached:
                try:
                    return pd.read_parquet(io.BytesIO(cached))
                except Exception as e:
                    logger.warning("Cache read failed: {}", e)
            result = func(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and not result.empty:
                buf = io.BytesIO()
                result.to_parquet(buf, index=False)
                buf.seek(0)
                r.setex(key, expire_seconds, buf.read())
            return result
        return wrapper
    return decorator
