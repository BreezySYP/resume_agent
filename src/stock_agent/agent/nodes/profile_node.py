"""agent/nodes/profile_node.py — 股票档案节点：单轮并行检索 + 池级精排降级。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from agent.tools import search_stock_profile
from event.decorator import node
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from loguru import logger
from pydantic import BaseModel, Field
from service.cuda_service import rerank
from shared.agents.agent_state import AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek
from shared.text.stock_text import build_stock_profile_text

PROFILE_TOP_K = 10  # 最终注入分析链路的股票池规模
KEYWORD_LIMIT = 5  # 单次关键词生成上限
PER_KEYWORD_TOP_K = 10  # 每个关键词的检索条数（池子上限约 50，rerank 负担可控）


class KeywordsPlan(BaseModel):
    keywords: list[str] = Field(description="搜索关键词")


def _extract_keywords(question: str) -> list[str]:
    """一次 LLM 调用生成搜索关键词；解析失败时降级为原始问题。"""
    prompt = HumanMessage(
        content=f"""
        用户问题：
        {question}

        不要回答问题。
        请提取{KEYWORD_LIMIT}个以内的搜索关键词。

        例如：
        芯片 -> 芯片、半导体、集成电路
        机器人 -> 机器人、工业机器人、人形机器人

        仅返回JSON：
        {{"keywords": []}}
    """
    )
    model = get_deepseek("deepseek-chat")
    parser = JsonOutputParser(pydantic_object=KeywordsPlan)
    try:
        resp = invoke_with_metrics(model, [prompt], "stock_profile", "deepseek-chat")
        plan = parser.parse(resp.content)
        keywords = [str(k).strip() for k in plan["keywords"] if str(k).strip()]
        if keywords:
            return keywords[:KEYWORD_LIMIT]
    except Exception as e:
        logger.warning("profile keyword extraction failed, fallback to raw question: {}", e)
    return [question]


def _search_keyword(kw: str) -> list[dict]:
    try:
        docs = search_stock_profile.invoke({"query": kw, "topk": PER_KEYWORD_TOP_K})
        if isinstance(docs, dict):
            docs = [docs]
        return docs or []
    except Exception as e:
        logger.warning("profile search failed for keyword {}: {}", kw, e)
        return []


def _search_all(keywords: list[str]) -> list[dict]:
    """并行检索所有关键词，单路失败不影响其他路。"""
    with ThreadPoolExecutor(max_workers=min(KEYWORD_LIMIT, len(keywords))) as pool:
        results = list(pool.map(_search_keyword, keywords))
    merged: list[dict] = []
    for docs in results:
        merged.extend(docs)
    return merged


def _dedup(records: list[dict]) -> list[dict]:
    """按 code 去重，保留首次出现。"""
    seen: dict[str, dict] = {}
    for r in records:
        code = r.get("code")
        if code is None:
            continue
        seen.setdefault(str(code), r)
    return list(seen.values())


def _rank(profiles: pd.DataFrame, question: str) -> pd.DataFrame:
    """池级 rerank 精排；rerank 失败时降级按 original_score 排序。"""
    df = profiles.copy()
    # 与 Qdrant 写入时一致，用 build_stock_profile_text 构造 rerank 文本；
    # scope 缺失/为空时用 business 兜底，避免 KeyError
    if "scope" not in df.columns:
        df["scope"] = ""
    mask = df["scope"].isna() | (df["scope"].astype(str).str.strip() == "")
    df.loc[mask, "scope"] = df["business"] if "business" in df.columns else ""
    try:
        scores = rerank(
            query=question,
            docs=[build_stock_profile_text(row) for _, row in df.iterrows()],
        )
        df["rerank_score"] = scores["rerank_score"]
        df = df.sort_values("rerank_score", ascending=False)
    except Exception as e:
        logger.warning("profile rerank failed, fallback to original_score: {}", e)
        df["rerank_score"] = df.get("original_score", 0.0)
        df = df.sort_values("original_score", ascending=False)
    return df


@node(node_name="profile", title="股票档案节点")
def profile_node(state: AgentState) -> dict:
    question = state.get("user_question") or ""
    keywords = _extract_keywords(question)
    profiles = _dedup(_search_all(keywords))
    if not profiles:
        return {"stock_profile": []}

    df = _rank(pd.DataFrame(profiles), question).head(PROFILE_TOP_K)
    if "scope" in df.columns:
        df = df.drop(columns=["scope"])
    records = df.to_dict(orient="records")
    return {"stock_profile": records}
