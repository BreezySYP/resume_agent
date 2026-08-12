"""
宏观评估 / LLM 指标（给 Grafana，不替代 LangSmith 明细）
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Optional

from prometheus_client import Counter, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST

# ---------------------------------------------------------------------------
# 评估分数：用 Histogram，便于看分布 + 算均值
# ---------------------------------------------------------------------------
EVAL_SCORE = Histogram(
    "agent_eval_score",
    "Agent evaluation scores (0-1)",
    labelnames=["metric"],  # faithfulness | answer_relevancy | profile_recall | profile_precision
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

EVAL_RUNS = Counter(
    "agent_eval_runs_total",
    "Evaluation runs",
    labelnames=["status"],  # ok | error
)

EVAL_DURATION = Histogram(
    "agent_eval_duration_seconds",
    "Full calculate_scores wall time",
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 180, 300),
)


def record_eval_scores(scores: dict) -> None:
    """写入 4 个评估分。"""
    for key in ("faithfulness", "answer_relevancy", "profile_recall", "profile_precision"):
        val = scores.get(key)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        # 夹紧到 [0, 1]，避免异常值污染直方图
        v = max(0.0, min(1.0, v))
        EVAL_SCORE.labels(metric=key).observe(v)


@contextmanager
def track_eval_run():
    """整段评估：耗时 + ok/error。"""
    t0 = time.perf_counter()
    try:
        yield
        EVAL_RUNS.labels(status="ok").inc()
    except Exception:
        EVAL_RUNS.labels(status="error").inc()
        raise
    finally:
        EVAL_DURATION.observe(time.perf_counter() - t0)


def metrics_response_body() -> bytes:
    return generate_latest()


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST