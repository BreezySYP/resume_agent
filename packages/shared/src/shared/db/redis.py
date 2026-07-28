"""shared/db/redis_cache.py — Redis DataFrame 缓存装饰器"""
import functools
import hashlib
import io
import json
from functools import wraps
from typing import AsyncGenerator
import pandas as pd
from loguru import logger
from redis import Redis
import asyncio
from shared.configs.settings import REDIS_URL
import inspect
from redis.asyncio import Redis as aRedis

redis_client = Redis.from_url(REDIS_URL)

async def async_redis_client():
    return await aRedis.from_url(REDIS_URL)

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
            cached = redis_client.get(key)
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
                redis_client.setex(key, expire_seconds, buf.read())
            return result
        return wrapper
    return decorator

import inspect
import json
from functools import wraps

def redis_cache(prefix: str, key: str, ttl: int = 1800):
    def decorator(func):
        sig = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            params = {
                k: v
                for k, v in bound.arguments.items()
                if k not in ("db", "session")
            }

            cache_key = f"{prefix}:{key.format(**params)}"

            cache = redis_client.get(cache_key)
            if cache is not None:
                return json.loads(cache)

            result = func(*args, **kwargs)
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result, ensure_ascii=False, default=str),
            )
            # logger.trace("set redis key for {}", cache_key)

            return result

        return wrapper

    return decorator

def delete(key: str):
    redis_client.delete(key)


def delete_pattern(pattern: str):
    for key in redis_client.scan_iter(pattern):
        redis_client.delete(key)


def push_queue( id: str, event: dict, prefix: str = "queue"):
    # 直接使用异步 Redis，不需要 run_coroutine_threadsafe
    result = redis_client.rpush(
        f"{prefix}:{id}",
        json.dumps(event)
    )
    logger.debug(f"push queue result: {result}")

def pop_queue(id: str, prefix: str = "queue"):
    data = redis_client.lpop(f"{prefix}:{id}")
    return json.loads(data) if data else None

async def sse_stream(id: str, prefix: str = "queue") -> AsyncGenerator[str, None]:
    """SSE 生成器：监听指定 job 的事件队列"""
    import json

    while True:
        event = pop_queue(id=id, prefix=prefix)
        if event is None:
            await asyncio.sleep(1)  # 队列为空时，稍作等待
            continue
        yield f"data: {json.dumps(event, default=str)}\n\n"
