"""agent/nodes/profile_node.py — 股票档案节点：单轮并行检索 + 池级精排降级。"""
from __future__ import annotations

import pandas as pd
from agent.tools import search_stock_profile
from event.decorator import node
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from loguru import logger
from pydantic import BaseModel, Field
from service.cuda_service import rerank
from shared.agents.agent_state import AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek
from shared.text.stock_text import build_stock_profile_text
from shared.threads import ContextThreadPoolExecutor

PROFILE_TOP_K = 10  # 最终注入分析链路的股票池规模
KEYWORD_LIMIT = 5  # 单次关键词生成上限
PER_KEYWORD_TOP_K = 10  # 每个关键词的检索条数（池子上限约 50，rerank 负担可控）
_REVIEW_POOL_SIZE = 30  # 交给 LLM 审核的 rerank 候选上限


class KeywordsPlan(BaseModel):
    keywords: list[str] = Field(description="搜索关键词")


class ProfileReviewResult(BaseModel):
    """点名股审核结果：用户点名时返回应保留的候选代码，否则空列表。"""

    keep_codes: list[str] = Field(
        description=(
            "应从候选股票中保留的代码；用户问题明确点名了候选中的股票则只返回这些，"
            "未点名或点名的股票不在候选列表中则返回空列表"
        )
    )


def _review_profiles(question: str, candidates: list[dict]) -> list[str]:
    """让 LLM 判断用户是否点名了股票，并返回候选池中应保留的代码。"""
    if not candidates:
        return []
    candidate_text = "\n".join(
        f"- {r.get('code')} {r.get('name')}：{(r.get('business') or '')[:100]}"
        for r in candidates
    )
    prompt = SystemMessage(
        content=f"""
        用户问题：
        {question}

        候选股票：
        {candidate_text}

        判断规则：
        - 如果用户问题明确点名了候选中的某只/某几只股票，只保留这些股票
        - 如果用户没有点名具体股票，或点名的股票不在候选列表中，返回空列表
        """
    )
    model = get_deepseek("deepseek-chat")
    try:
        result = invoke_with_metrics(
            model.with_structured_output(ProfileReviewResult),
            [prompt],
            "profile_review",
            "deepseek-chat",
        )
        return list(result.keep_codes)
    except Exception as e:
        logger.warning("profile review failed, fallback to top{}: {}", PROFILE_TOP_K, e)
        return []


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
    with ContextThreadPoolExecutor(max_workers=min(KEYWORD_LIMIT, len(keywords))) as pool:
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

    df = _rank(pd.DataFrame(profiles), question)
    if "scope" in df.columns:
        df = df.drop(columns=["scope"])
    ranked = df.to_dict(orient="records")

    # 用户点名股票时只保留点名股；LLM 未给出代码则维持 top10
    keep_codes = _review_profiles(question, ranked[:_REVIEW_POOL_SIZE])
    if keep_codes:
        keep = {str(code) for code in keep_codes}
        filtered = [r for r in ranked if str(r.get("code")) in keep][:PROFILE_TOP_K]
        if filtered:
            return {"stock_profile": filtered}
        logger.warning("profile review keep_codes 与候选池无交集，回退 top{}", PROFILE_TOP_K)

    return {"stock_profile": ranked[:PROFILE_TOP_K]}
