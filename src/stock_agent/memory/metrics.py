"""memory 模块 Prometheus 指标（给 Grafana）。

采集点集中在 stock_agent：
- MemoryService 门面：操作量/延迟、写入动作、召回质量、整合任务、TTL 数据质量
- StockMemoryStore：Qdrant 依赖健康

所有埋点均为“尽力而为”：记录失败只记 debug 日志，绝不影响业务。
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# 操作层：调用量 / 延迟（status: ok | error）
# ---------------------------------------------------------------------------
MEMORY_OPERATIONS = Counter(
    "memory_operations_total",
    "Memory service operations",
    labelnames=["operation", "status"],
)

MEMORY_OPERATION_DURATION = Histogram(
    "memory_operation_duration_seconds",
    "Memory service operation latency",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10),
)

# ---------------------------------------------------------------------------
# 写入：动作分布（created / deduplicated / superseded / skipped）
# ---------------------------------------------------------------------------
MEMORY_WRITES = Counter(
    "memory_writes_total",
    "Memory writes by action",
    labelnames=["memory_type", "action"],
)

# ---------------------------------------------------------------------------
# 召回质量（agent 路径 search_for_prompt）
# ---------------------------------------------------------------------------
MEMORY_RECALL_MISS = Counter(
    "memory_recall_miss_total",
    "Agent recall returned no memory",
)

MEMORY_RECALL_RESULTS = Histogram(
    "memory_recall_results_count",
    "Number of memories recalled per query",
    buckets=(0, 1, 2, 3, 4, 5, 6, 8, 10, 15, 20),
)

MEMORY_RECALL_PROMPT_CHARS = Histogram(
    "memory_recall_prompt_chars",
    "Injected memory context length (chars)",
    buckets=(100, 300, 500, 800, 1200, 2000, 3000, 5000),
)

# ---------------------------------------------------------------------------
# 规模
# ---------------------------------------------------------------------------
MEMORY_ACTIVE_COUNT = Gauge(
    "memory_active_count",
    "Active (non-expired) memory count",
    labelnames=["memory_type"],  # all | profile | episode | procedural | summary
)

# ---------------------------------------------------------------------------
# 整合：episode → summary
# ---------------------------------------------------------------------------
MEMORY_CONSOLIDATION_RUNS = Counter(
    "memory_consolidation_runs_total",
    "Episode→summary consolidation runs",
    labelnames=["status"],  # ok | error
)

MEMORY_CONSOLIDATION_DURATION = Histogram(
    "memory_consolidation_duration_seconds",
    "Consolidation wall time",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

MEMORY_CONSOLIDATION_OUTPUT = Counter(
    "memory_consolidation_output_total",
    "Summaries created by consolidation",
)

# ---------------------------------------------------------------------------
# Qdrant 依赖（operation: search | upsert）
# ---------------------------------------------------------------------------
MEMORY_VECTOR_OPS = Counter(
    "memory_vector_ops_total",
    "Qdrant vector operations",
    labelnames=["operation", "status"],
)

MEMORY_VECTOR_DURATION = Histogram(
    "memory_vector_duration_seconds",
    "Qdrant vector operation latency",
    labelnames=["operation"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)

# ---------------------------------------------------------------------------
# TTL 数据质量
# ---------------------------------------------------------------------------
MEMORY_TTL = Histogram(
    "memory_ttl_seconds",
    "Assigned TTL of newly written memories",
    labelnames=["memory_type"],
    buckets=(60, 300, 900, 3600, 86400, 604800, 2592000, 7776000, 15552000),
)

MEMORY_ANOMALOUS_TTL = Counter(
    "memory_anomalous_ttl_total",
    "Writes whose expires_at is not after creation (data quality)",
    labelnames=["memory_type"],
)


def _safe(action: Callable[[], Any]) -> None:
    """指标记录尽力而为，失败只记 debug 日志。"""
    try:
        action()
    except Exception as e:  # noqa: BLE001
        logger.debug("memory metric recording failed: {}", e)


@contextmanager
def track_memory_operation(operation: str):
    """操作级埋点：成功/失败计数 + 耗时（异常时计数 error 并继续抛出）。"""
    t0 = time.perf_counter()
    try:
        yield
    except Exception:
        _safe(lambda: MEMORY_OPERATIONS.labels(operation=operation, status="error").inc())
        raise
    else:
        _safe(lambda: MEMORY_OPERATIONS.labels(operation=operation, status="ok").inc())
    finally:
        _safe(
            lambda: MEMORY_OPERATION_DURATION.labels(operation=operation).observe(
                time.perf_counter() - t0
            )
        )


@contextmanager
def track_consolidation():
    """整合任务埋点：ok/error 计数 + 耗时。"""
    t0 = time.perf_counter()
    try:
        yield
    except Exception:
        _safe(lambda: MEMORY_CONSOLIDATION_RUNS.labels(status="error").inc())
        raise
    else:
        _safe(lambda: MEMORY_CONSOLIDATION_RUNS.labels(status="ok").inc())
    finally:
        _safe(lambda: MEMORY_CONSOLIDATION_DURATION.observe(time.perf_counter() - t0))


@contextmanager
def track_vector_operation(operation: str):
    """Qdrant 操作埋点：ok/error 计数 + 耗时。"""
    t0 = time.perf_counter()
    try:
        yield
    except Exception:
        _safe(lambda: MEMORY_VECTOR_OPS.labels(operation=operation, status="error").inc())
        raise
    else:
        _safe(lambda: MEMORY_VECTOR_OPS.labels(operation=operation, status="ok").inc())
    finally:
        _safe(
            lambda: MEMORY_VECTOR_DURATION.labels(operation=operation).observe(
                time.perf_counter() - t0
            )
        )


def record_memory_write(memory_type: str, action: str) -> None:
    """写入动作：created / deduplicated / superseded / skipped。"""
    _safe(lambda: MEMORY_WRITES.labels(memory_type=memory_type, action=action).inc())


def record_recall(items_count: int, prompt_text: str) -> None:

    
    """agent 召回路径：空结果计数 + 返回条数分布 + 注入上下文长度。"""
    _safe(lambda: MEMORY_RECALL_RESULTS.observe(items_count))
    _safe(lambda: MEMORY_RECALL_PROMPT_CHARS.observe(len(prompt_text)))
    if items_count == 0:
        _safe(lambda: MEMORY_RECALL_MISS.inc())


def set_active_count(memory_type: str, count: int) -> None:
    """机会性更新有效记忆规模 Gauge（count_memories 调用时）。"""
    _safe(lambda: MEMORY_ACTIVE_COUNT.labels(memory_type=memory_type).set(count))


def record_consolidation_output(count: int) -> None:
    _safe(lambda: MEMORY_CONSOLIDATION_OUTPUT.inc(count))


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def record_ttl(memory_type: str, created_at: Optional[datetime], expires_at: Optional[datetime]) -> None:
    """TTL 分布；expires_at ≤ created_at 视为数据异常只进 anomalous 计数。"""
    if expires_at is None:
        return
    try:
        created = _to_naive_utc(created_at) if created_at is not None else datetime.utcnow()
        ttl = (_to_naive_utc(expires_at) - created).total_seconds()
        if ttl <= 0:
            _safe(lambda: MEMORY_ANOMALOUS_TTL.labels(memory_type=memory_type).inc())
            return
        _safe(lambda: MEMORY_TTL.labels(memory_type=memory_type).observe(ttl))
    except Exception as e:  # noqa: BLE001
        logger.debug("memory ttl metric recording failed: {}", e)
