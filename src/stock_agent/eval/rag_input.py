"""eval/rag_input.py — RAG 输入与代码提取的公共逻辑。

eval_node 把 AgentState 解析成 rag_context 列表；feedback / dry-run API 直接
消费 rag_context / question / answer 三个参数；这里统一来源识别与代码提取。
"""

from __future__ import annotations

import re
from typing import Any, Dict

_TECHNICAL_KEYS = {
    "trend_score",
    "momentum_score",
    "volume_score",
    "total_technical_score",
    "technical_rank",
}
_FINANCIAL_KEYS = {
    "profitability_score",
    "growth_score",
    "quality_score",
    "safety_score",
    "total_score",
    "total_financial_score",
    "total_financial_rank",
    "revenue_growth",
    "profit_growth",
    "net_margin",
    "roe",
    "roa",
    "operating_cashflow",
    "asset_liability_ratio",
}
_PROFILE_KEYS = {"business", "scope"}
_NEWS_KEYS = {"title", "url", "mediaName", "content"}
_SOURCES = {"profile", "financial", "technical", "news", "memory"}


def _detect_source(item) -> str:
    """判断单条 RAG 记录属于哪个来源；支持显式 source 字段或按字段自动识别。"""
    if isinstance(item, str):
        return "news"
    if not isinstance(item, dict):
        return "news"
    source = item.get("source")
    if source in _SOURCES:
        return source
    if "memory" in item:
        return "memory"
    if _TECHNICAL_KEYS & item.keys():
        return "technical"
    if _FINANCIAL_KEYS & item.keys():
        return "financial"
    if _PROFILE_KEYS & item.keys() and "code" in item:
        return "profile"
    if _NEWS_KEYS & item.keys():
        return "news"
    return "news"


def state_to_rag_context(state: Dict[str, Any]) -> list:
    """把 AgentState 的结构化字段解析成 rag_context 列表（每条带 source 标记）。"""
    rag: list = []
    for field, source in (
        ("stock_profile", "profile"),
        ("stock_technique_factor", "technical"),
        ("stock_financial_factor", "financial"),
    ):
        for record in state.get(field) or []:
            item = dict(record) if isinstance(record, dict) else record
            if isinstance(item, dict):
                item.setdefault("source", source)
            rag.append(item)
    for record in state.get("news_items") or []:
        item = dict(record) if isinstance(record, dict) else record
        if isinstance(item, dict):
            item.setdefault("source", "news")
        rag.append(item)
    memory = (state.get("memory_context") or "").strip()
    if memory:
        rag.append({"source": "memory", "memory": memory})
    return rag


def retrieved_codes(rag_context: list) -> list[str]:
    """提取 rag_context 中股票档案（profile）记录里的代码，作为检索池。"""
    codes: list[str] = []
    for item in rag_context:
        if isinstance(item, dict) and _detect_source(item) == "profile":
            code = item.get("code")
            if code is not None:
                codes.append(str(code))
    return codes


def extract_cited_codes(answer: str, universe: set[str]) -> set[str]:
    """从最终回答里解析实际引用的 A 股代码，只保留出现在 universe 内的代码，
    避免把正文里的普通 6 位数字误当成股票代码。"""
    if not answer:
        return set()
    codes = set(re.findall(r"[（(]\s*(\d{6})\s*[)）]", answer))
    codes |= set(re.findall(r"(?<![0-9])\d{6}(?![0-9])", answer))
    return {c for c in codes if c in universe}
