# shared/events/decorator.py

from datetime import date, datetime
from decimal import Decimal
from functools import wraps

import numpy as np
import pandas as pd
from event.event_manager import event


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

        @wraps(func)
        def wrapper(state, *args, **kwargs):
            thread_id = state["thread_id"]
            event.node_start(
                thread_id,
                node_name,
                title,
            )
            try:
                result = func(normalize(state), *args, **kwargs)
                event.node_finish(
                    thread_id,
                    node_name,
                )
                return normalize(result)
            except Exception as e:
                event.node_error(
                    thread_id,
                    node_name,
                    str(e),
                )
                raise
            
        return wrapper
    return decorator

        