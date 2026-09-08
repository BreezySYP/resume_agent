"""agent/nodes/news_node.py — 新闻数据节点（单次检索 + 单次结构化 LLM 输出）。

不再使用 create_agent：把所有股票名合成一次 search_news，把检索到的新闻连同
id 一起放进 prompt，再只调一次 DeepSeek 用 with_structured_output 输出
{content, cited_news_ids}，既省成本又避免自由文本 JSON 解析失败。
"""

from typing import Any, Dict, List

from agent.tools import search_news, time_tool
from event.decorator import node
from langchain_core.messages import SystemMessage
from loguru import logger
from pydantic import BaseModel, Field
from shared.agents.agent_state import AgentState
from shared.metrics.prome import invoke_with_metrics
from shared.models.deepseek import get_deepseek

_NEWS_TOP_K = 30  # 单次检索返回的新闻条数上限（覆盖全部股票）
_NEWS_PROMPT_MAX_ARTICLES = 20  # 放进 prompt 的新闻条数上限
_NEWS_CONTENT_CHARS = 300  # 每条新闻正文截断长度，控制 prompt 大小

# 只保留证据需要的字段，丢弃 embedding/fetch_time/分数等元数据与大字段，
# 避免污染 faithfulness 上下文与 state/checkpoint。
_NEWS_KEEP_FIELDS = (
    "id",
    "code",
    "name",
    "title",
    "content",
    "summary",
    "date",
    "url",
    "mediaName",
    "source_type",
    "importance_score",
    "sector",
)


class NewsAnalysisResult(BaseModel):
    """新闻分析的结构化输出：逐句标注引用的正文 + 全部引用新闻 id。"""

    content: str = Field(description="带【新闻id】标注的逐句分析正文")
    cited_news_ids: list[int] = Field(
        default_factory=list,
        description="content 中实际引用的全部新闻 id，不含无；无法给出时可为空列表",
    )


def _news_dedup_key(record: dict):
    """记录去重键：优先 id，其次 url，再退 title+date；无可识别标识返回 None。"""
    for key in ("id", "url"):
        value = record.get(key)
        if value is not None:
            return ("k", str(value))
    title, date = record.get("title"), record.get("date")
    if title is not None or date is not None:
        return ("t", str(title), str(date))
    return None


def _dedup_news(records: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for record in records:
        key = _news_dedup_key(record)
        if key is None:
            out.append(record)
        elif key not in seen:
            seen.add(key)
            out.append(record)
    return out


def _strip_news_record(record: dict) -> dict:
    return {k: record[k] for k in _NEWS_KEEP_FIELDS if k in record}


def _search_news(names: list[str]) -> List[dict]:
    """把所有股票名合成一次检索；失败返回空列表不影响主流程。"""
    try:
        docs = search_news.invoke({"stock_names": " ".join(names), "topk": _NEWS_TOP_K})
        if isinstance(docs, dict):
            docs = [docs]
        return docs if isinstance(docs, list) else []
    except Exception as e:
        logger.warning("news search failed: {}", e)
        return []


def _filter_news_items_by_cited(records: List[dict], cited_ids: List[int]) -> List[dict]:
    """只保留被引用的新闻记录；cited_ids 为空时保留全部（避免解析失败误删）。"""
    if not cited_ids:
        return records
    cited = {str(i) for i in cited_ids}
    return [r for r in records if r.get("id") is not None and str(r["id"]) in cited]


def _build_news_prompt(
    current_time: str,
    stock_names: str,
    news_records: List[dict],
) -> SystemMessage:
    """构造新闻分析 prompt：把检索到的新闻（id+标题+正文）放进 prompt 供模型引用。"""
    articles = []
    for record in news_records[:_NEWS_PROMPT_MAX_ARTICLES]:
        content = (record.get("content") or "")[:_NEWS_CONTENT_CHARS]
        articles.append(f"[{record.get('id')}] {record.get('name', '')} {record.get('title', '')}\n{content}")
    news_text = "\n\n".join(articles) if articles else "（无新闻数据）"

    return SystemMessage(content=f"""
        你是新闻分析师。
        当前日期：{current_time}

        针对以下股票：
        {stock_names}

        新闻数据（每篇以 [新闻id] 开头）：
        {news_text}

        重点维度：情绪、政策利好、机构、风险、热点。

        输出要求（必须遵守）：
        - 直接输出最终分析正文，不要输出任何思考过程、解释或前言（禁止以"我需要先…"、"好的"等开头）
        - content 按句子逐句书写，每个句子末尾标注该句引用的新闻 id，格式：【新闻id: 368541】或【新闻id: 368541, 368542】；句子没有对应新闻依据时标注【新闻id: 无】
        - cited_news_ids 汇总 content 中实际引用的所有 id，不含"无"；引用 id 只能来自上面新闻数据里的 [新闻id]
        - 正文只能基于上面提供的新闻数据书写，不得编造新闻或使用模型自身知识
        """)


@node(node_name="news", title="新闻数据节点")
def news_node(state: AgentState) -> Dict[str, Any]:
    profiles = state.get("stock_profile") or []
    names = [p.get("name") for p in profiles if isinstance(p, dict) and p.get("name")]
    if not names:
        return {
            "news_analysis": "No stock profile available.",
            "news_items": [],
            "news_analysis_summary": "",
            "news_cited_ids": [],
        }

    current_time = state.get("current_time", time_tool.invoke(""))
    records = [_strip_news_record(r) for r in _dedup_news(_search_news(names))]

    model_name = "deepseek-chat"
    model = get_deepseek(model=model_name, temperature=0.2)
    prompt = _build_news_prompt(current_time, " ".join(names), records)
    structured_llm = model.with_structured_output(NewsAnalysisResult)
    try:
        result = invoke_with_metrics(structured_llm, [prompt], "news", model_name)
        content = str(result.content)
        cited_ids = [int(i) for i in (result.cited_news_ids or [])]
    except Exception as e:
        logger.exception("news structured analysis failed: {}", e)
        content = "新闻分析生成失败。"
        cited_ids = []

    news_items = _filter_news_items_by_cited(records, cited_ids)
    return {
        "news_analysis": content,
        "news_items": news_items,
        "news_analysis_summary": content,
        "news_cited_ids": cited_ids,
    }
