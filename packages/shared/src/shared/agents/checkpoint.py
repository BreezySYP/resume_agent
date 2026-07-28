
from contextlib import contextmanager

from langgraph.checkpoint.redis import RedisSaver
from shared.configs.settings import REDIS_URL

@contextmanager
def get_redis_checkpointer():
    with RedisSaver.from_conn_string(REDIS_URL) as cp:
        cp.setup()
        yield cp

