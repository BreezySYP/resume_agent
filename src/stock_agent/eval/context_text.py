"""上下文条目 → 可读证据文本 的解析工具。

线上上下文（因子记录、新闻检索结果、档案等）里混着多种形态：dict、dict 的字符串 repr
（可能含 HTML 标签、字面 \\uXXXX 转义、pandas Timestamp）、截断的半截 JSON，
以及普通字符串。本模块统一把这些形态清洗成干净的正文文本，供 faithfulness 等评测
做分句与证据检索。
"""
from __future__ import annotations

import ast
import html
import json
import re

# 抽取证据时跳过元数据字段（id/url/分数/时间/keywords 等，不属于正文）
_SKIP_KEYS = {
    "id",
    "code",
    "url",
    "image",
    "images",
    "fetch_time",
    "update_time",
    "original_score",
    "rerank_score",
    "score",
    "keywords",
    "sector",
    "source",
    "source_type",
    "importance_score",
    "date",
    "time",
    "timestamp",
    "status",
    "query",
    "follow_up_questions",
    "page",
    "total",
}

_JUNK_PATTERN = re.compile(
    r"^(?:https?://|www\.)|^[\d.,%\-—\s]+$|^(?:None|nan|null)$|^\d{4}-\d{2}-\d{2}",
    re.I,
)
_LEADING_JUNK_RE = re.compile(
    r"^\s*(?:https?://\S+|www\.\S+|\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?|"
    r"None|nan|null|[\d.,%\-—]+\s+)",
    re.I,
)


def clean_text(text: str) -> str:
    """清洗证据文本：去 HTML 标签/实体、字面 \\uXXXX 序列、Timestamp repr，规范化空白。"""
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"<[^>]+>", "", s)  # HTML 标签（<em>、<br> 等）
    s = html.unescape(s)  # &amp; &lt; 等实体
    s = re.sub(
        r"\\+u([0-9a-fA-F]{4})",
        lambda m: chr(int(m.group(1), 16)),
        s,
    )  # 字面 \u3000 序列（兼容 \\u 双重转义）
    s = re.sub(r"\\+[nt]", " ", s)  # 字面 \n \t
    s = re.sub(r"Timestamp\('([^']*)'\)", r"\1", s)  # pandas Timestamp repr
    s = s.replace("\u3000", " ")  # 全角空格
    s = re.sub(r"\s+", " ", s)
    return s.strip()


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


def clean_truncated_repr(text: str) -> str:
    """对解析失败的截断 repr 做轻量清理：去掉 'key': 前缀后抽取字符串值（正文）。"""
    s = text.strip()
    if s.startswith("{"):
        s = s[1:]
    if s.endswith("}"):
        s = s[:-1]
    s = re.sub(r"'[^']{1,40}':\s*", "", s)
    values = re.findall(r"'((?:[^'\\]|\\.)*)'", s)
    if not values:
        values = re.findall(r'"((?:[^"\\]|\\.)*)"', s)
    return clean_text("\n".join(values))


def _strip_leading_junk(text: str) -> str:
    """剥离句子开头的 URL/日期/None/纯数字等垃圾 token，避免有效正文被连坐丢弃。"""
    s = text
    while True:
        m = _LEADING_JUNK_RE.match(s)
        if not m:
            return s
        s = s[m.end() :]


def context_to_text(ctx: object) -> str:
    """把各种形态的上下文条目转成可读正文，而不是 key:value 墙。"""
    if isinstance(ctx, str):
        parsed = parse_repr(ctx)
        if parsed is not None:
            return context_to_text(parsed)
        if ctx.strip().startswith(("{", "[")):
            return clean_truncated_repr(ctx)
        return clean_text(ctx)
    if isinstance(ctx, dict):
        parts: list[str] = []
        if "name" in ctx and "code" in ctx:
            parts.append(f"{ctx['name']}（{ctx['code']}）")
        for k, v in ctx.items():
            if k in _SKIP_KEYS or k in ("name", "code"):
                continue
            if isinstance(v, (dict, list)):
                sub = context_to_text(v)
                if sub:
                    parts.append(sub)
            elif isinstance(v, str):
                cleaned = clean_text(v)
                if len(cleaned) >= 4:
                    parts.append(cleaned)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                # 因子分数等数字字段也纳入证据（如 profitability_score: 0.72）
                parts.append(f"{k}: {v}")
        return "\n".join(parts)
    if isinstance(ctx, list):
        return "\n".join(context_to_text(x) for x in ctx if context_to_text(x))
    return clean_text(str(ctx))


def split_sentences(text: str, min_len: int = 8) -> list[str]:
    """清洗后按中英文句末标点分句，避免把小数点当成句号；去重、过滤短碎片与垃圾。"""
    text = clean_text(text)
    if not text:
        return []

    # 1. 中文句子结束符：无条件切
    # 2. 英文 .!? ：后接非字母数字才切（排除 120.3、3.14、603986.SH 后缀）
    pattern = r"(?<=[。！？；!?;])\s*|(?<!\d)(?<=[.!?])(?![\d\w])\s*|\n+"

    parts = re.split(pattern, text)

    sentences: list[str] = []
    seen: set[str] = set()
    for s in parts:
        s = clean_text(s)
        s = _strip_leading_junk(s)
        if len(s) < min_len or _JUNK_PATTERN.search(s):
            continue
        if s in seen:
            continue
        seen.add(s)
        sentences.append(s)
    return sentences
