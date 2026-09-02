"""shared.threads.ContextThreadPoolExecutor 单测：任务继承提交方 context。"""
import contextvars
from concurrent.futures import ThreadPoolExecutor

from shared.threads import ContextThreadPoolExecutor


def test_context_thread_pool_propagates_context():
    var = contextvars.ContextVar("trace_ctx", default="default")
    # 池先创建（此时 context 是 default），之后提交方的 context 才变化
    pool = ContextThreadPoolExecutor(max_workers=1)
    try:
        var.set("parent")
        assert pool.submit(var.get).result() == "parent"
    finally:
        pool.shutdown()


def test_plain_thread_pool_does_not_propagate():
    var = contextvars.ContextVar("trace_ctx", default="default")
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        var.set("parent")
        assert pool.submit(var.get).result() == "default"
    finally:
        pool.shutdown()
