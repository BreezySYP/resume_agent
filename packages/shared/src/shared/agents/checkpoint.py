
import asyncio
from contextlib import asynccontextmanager, contextmanager

from langgraph.checkpoint.redis import RedisSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from shared.configs.settings import REDIS_URL


@contextmanager
def get_redis_checkpointer():
    with RedisSaver.from_conn_string(REDIS_URL) as cp:
        cp.setup()
        yield cp


@asynccontextmanager
async def get_aredis_checkpointer():
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as cp:
        await cp.setup()
        yield cp


_shared_aredis: AsyncRedisSaver | None = None
_shared_aredis_lock: asyncio.Lock | None = None


async def get_shared_aredis_checkpointer() -> AsyncRedisSaver:
    """复用同一个 AsyncRedisSaver 实例（进程内只 setup 一次）。

    每个请求都新建连接 + 重复跑索引检查，并发时会把 Redis 连接打爆
    （Connection refused）。高频只读端点（对话历史等）应使用本函数。
    """
    global _shared_aredis, _shared_aredis_lock
    if _shared_aredis_lock is None:
        _shared_aredis_lock = asyncio.Lock()
    if _shared_aredis is None:
        async with _shared_aredis_lock:
            if _shared_aredis is None:
                saver = AsyncRedisSaver(redis_url=REDIS_URL)
                await saver.asetup()
                await saver.aset_client_info()
                _shared_aredis = saver
    return _shared_aredis
