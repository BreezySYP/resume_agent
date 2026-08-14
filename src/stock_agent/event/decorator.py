# shared/events/decorator.py

import inspect
from datetime import date, datetime
from decimal import Decimal
from functools import wraps

import numpy as np
import pandas as pd
from event.event_manager import event
from loguru import logger
from shared.configs.tracing import get_tracer, span_error

_tracer = get_tracer("agent.nodes")


def normalize(obj):
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [normalize(v) for v in obj]

    if isinstance(obj, tuple):
        return tuple(normalize(v) for v in obj)

    return obj


def node(node_name: str, title: str):

    def decorator(func):

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(state, *args, **kwargs):
                thread_id = state.get("thread_id", "")
                job_id = state.get("job_id", "")
                event.node_start(
                    job_id,
                    node_name,
                    title,
                )
                with _tracer.start_as_current_span(
                    f"node.{node_name}",  # Span 名称
                    attributes={
                        "node.name": node_name,
                        "node.title": title,
                        "thread.id": thread_id,
                        "job.id": str(job_id),
                        "state.keys": list(state.keys()) if isinstance(state, dict) else None,
                    }
                ) as span:
                    try:
                        result = await func(normalize(state), *args, **kwargs)
                        event.node_finish(job_id, node_name)
                        return normalize(result)
                    except Exception as e:
                        # 3. 记录错误到 Span
                        span_error(span, e)
                        # 发送错误事件
                        event.node_error(job_id, node_name, str(e))
                        logger.exception(e)
                        raise

            return wrapper
        @wraps(func)
        def sync_wrapper(state, *args, **kwargs):
            thread_id = state.get("thread_id", "")
            job_id = state.get("job_id", "")

            event.node_start(
                job_id,
                node_name,
                title,
            )

            with _tracer.start_as_current_span(
                f"node.{node_name}",
                attributes={
                    "node.name": node_name,
                    "node.title": title,
                    "thread.id": thread_id,
                    "job.id": str(job_id),
                    "state.keys": list(state.keys()) if isinstance(state, dict) else None,
                }
            ) as span:

                try:
                    result = func(normalize(state), *args, **kwargs)

                    event.node_finish(job_id, node_name)

                    return normalize(result)

                except Exception as e:
                    span_error(span, e)

                    event.node_error(
                        job_id,
                        node_name,
                        str(e),
                    )
                    logger.exception(e)
                    raise

        return sync_wrapper
    return decorator
