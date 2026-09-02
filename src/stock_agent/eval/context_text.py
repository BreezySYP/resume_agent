"""eval/context_text.py — RAG 记录字符串 repr / JSON 的解析工具。"""

from __future__ import annotations

import ast
import json
import re


def parse_repr(text: str) -> object | None:
    """字符串以 { 或 [ 开头时，尝试解析成 dict/list（dict repr / JSON），失败返回 None。"""
    stripped = text.strip()
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return None
    # pandas Timestamp 不是合法字面量，先替换成 None 再解析
    stripped = re.sub(r"Timestamp\([^)]*\)", "None", stripped)
    for loader in (ast.literal_eval, json.loads):
        try:
            return loader(stripped)
        except Exception:
            continue
    return None
