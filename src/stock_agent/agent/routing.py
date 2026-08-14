"""agent/routing.py — 图路由决策（纯函数，便于单测）"""

from __future__ import annotations

from typing import Any


def should_continue(state: dict[str, Any]) -> str:
    """Reflection 后的路由决策：重试次数用尽或 Reflection 通过则写记忆，否则回到合成节点。"""
    reflections = state.get("reflections") or []
    last_reflection = (reflections[-1] if reflections else "").upper()
    retry_count = state.get("retry_count", 0)

    if retry_count >= 3 or "PASS" in last_reflection:
        return "memory_write"
    return "synthesizer"
