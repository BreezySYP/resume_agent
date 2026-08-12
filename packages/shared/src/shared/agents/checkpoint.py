
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

