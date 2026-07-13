import asyncio
from typing import AsyncGenerator
import json
from shared.db.redis_cache import redis_client, async_redis_client
from loguru import logger




def push_event( thread_id: str, event: dict):
    # 直接使用异步 Redis，不需要 run_coroutine_threadsafe
    result = redis_client.rpush(
        f"queue:{thread_id}",
        json.dumps(event)
    )
    logger.debug(f"push_event result: {result}")

def pop_event(thread_id: str):
    data = redis_client.lpop(f"queue:{thread_id}")
    return json.loads(data) if data else None




async def sse_stream(thread_id: str) -> AsyncGenerator[str, None]:
    """SSE 生成器：监听指定 job 的事件队列"""
    import json

    while True:
        event = pop_event(thread_id=thread_id)
        if event is None:
            yield f"data: {json.dumps({'done': True})}\n\n"
            break
        yield f"data: {json.dumps(event, default=str)}\n\n"

## 2026-07-12 13:43:11.475 | DEBUG    | event.queue_manager:push_event:16 - push_event result: 26
# Blocked deserialization of method call pandas.Timestamp.fromisoformat - not in allowed methods set.