import time
from typing import Any

from prometheus_client import Counter, Histogram


# ---------------------------------------------------------------------------
# LLM 宏观（若全局 ainvoke 已埋点可复用；这里给一份独立实现）
# ---------------------------------------------------------------------------
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM API calls",
    labelnames=["model", "status", "source"],  # ok | error
)

LLM_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM call latency",
    labelnames=["model", "source"],  # ainvoke | invoke
    buckets=(0.3, 0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89),
)

LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    labelnames=["model", "type", "source"],  # input | output | reasoning | total
)


def extract_usage(response: Any) -> dict:
    """从 AIMessage 提取 token。"""
    if getattr(response, "usage_metadata", None):
        u = response.usage_metadata or {}
        reasoning = (u.get("output_token_details") or {}).get("reasoning") or 0
        return {
            "input": int(u.get("input_tokens") or 0),
            "output": int(u.get("output_tokens") or 0),
            "reasoning": int(reasoning or 0),
            "total": int(u.get("total_tokens") or 0),
        }

    meta = getattr(response, "response_metadata", None) or {}
    tu = meta.get("token_usage") or meta.get("usage") or {}
    details = tu.get("completion_tokens_details") or {}
    return {
        "input": int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0),
        "output": int(tu.get("completion_tokens") or tu.get("output_tokens") or 0),
        "reasoning": int(details.get("reasoning_tokens") or 0),
        "total": int(tu.get("total_tokens") or 0),
    }



def observe_llm_call(
    *,
    model: str,
    elapsed: float,
    source: str,
    response: Any = None,
    error: bool = False,
) -> None:
    status = "error" if error else "ok"
    LLM_REQUESTS.labels(model=model, status=status, source=source).inc()
    LLM_DURATION.labels(model=model, source=source).observe(elapsed)
    if error or response is None:
        return
    usage = extract_usage(response)
    for t, n in usage.items():
        if n:
            LLM_TOKENS.labels(model=model, type=t, source=source).inc(n)


async def ainvoke_with_metrics(model, prompt, source, model_name):
    """带宏观埋点的 ainvoke。"""
    t0 = time.perf_counter()
    try:
        resp = await model.ainvoke(prompt)
        observe_llm_call(
            model=model_name,
            elapsed=time.perf_counter() - t0,
            source=source,
            response=resp,
            error=False,
        )
        return resp
    except Exception:
        observe_llm_call(
            model=model_name,
            elapsed=time.perf_counter() - t0,
            source=source,
            error=True,
        )
        raise

def invoke_with_metrics(model, prompt,source, model_name):
    """带宏观埋点的 ainvoke。"""
    t0 = time.perf_counter()
    try:
        resp = model.invoke(prompt)
        observe_llm_call(
            model=model_name,
            elapsed=time.perf_counter() - t0,
            source=source,
            response=resp,
            error=False,
        )
        return resp
    except Exception:
        observe_llm_call(
            model=model_name,
            elapsed=time.perf_counter() - t0,
            source=source,
            error=True,
        )
        raise