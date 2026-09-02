"""shared/threads.py — 透传 contextvars 的线程池。

LangSmith/LangChain 用 contextvars 维护 run 树父子关系，而 ThreadPoolExecutor
的 worker 不继承提交方的 context，导致跨线程的工具调用变成顶层 trace。
每个任务包一层 copy_context()，让子 run 正确挂到父 run 下。
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    """每个任务都在提交方的 contextvars 上下文中执行。"""

    def submit(self, fn, /, *args, **kwargs):
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)
