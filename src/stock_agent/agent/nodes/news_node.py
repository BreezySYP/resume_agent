"""agent/nodes/news_node.py — 新闻数据节点（确定性检索 + 单次结构化 LLM 输出）。

不再使用 create_agent：按股票名并行检索新闻，收集记录后只调一次 DeepSeek，
用 with_structured_output 强制输出 {content, cited_news_ids}，既省成本又避免
自由文本 JSON 解析失败。
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
from shared.threads import ContextThreadPoolExecutor

_NEWS_TOP_K = 5
_MAX_NEWS_WORKERS = 5

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
    cited_news_ids: list[int] = Field(description="content 中实际引用的全部新闻 id，不含无")


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


def _search_stock_news(name: str) -> List[dict]:
    """按股票名检索一次新闻；单只失败不影响其他股票。"""
    try:
        docs = search_news.invoke({"stock_names": name, "topk": _NEWS_TOP_K})
        if isinstance(docs, dict):
            docs = [docs]
        return docs if isinstance(docs, list) else []
    except Exception as e:
        logger.warning("news search failed for {}: {}", name, e)
        return []


def _filter_news_items_by_cited(records: List[dict], cited_ids: List[int]) -> List[dict]:
    """只保留被引用的新闻记录；cited_ids 为空时保留全部（避免解析失败误删）。"""
    if not cited_ids:
        return records
    cited = {str(i) for i in cited_ids}
    return [r for r in records if r.get("id") is not None and str(r["id"]) in cited]


def _build_news_prompt(current_time: str, stock_names: str, stock_profile: Any) -> SystemMessage:
    """构造新闻分析 prompt：最终 content 逐句标注引用的新闻 id。"""
    return SystemMessage(content=f"""
        你是新闻分析师。
        当前日期：{current_time}

        针对以下股票：
        {stock_names}

        概念：
        {stock_profile}分析**最新**新闻对股价的影响

        重点维度：情绪、政策利好、机构、风险、热点。

        输出要求（必须遵守）：
        - content 按句子逐句书写，每个句子末尾标注该句引用的新闻 id，格式：【新闻id: 368541】或【新闻id: 368541, 368542】；句子没有对应新闻依据时标注【新闻id: 无】
        - cited_news_ids 汇总 content 中实际引用的所有 id，不含"无"；引用 id 只能来自 search_news 的搜索结果
        - 正文内容按实际分析书写，不得编造新闻
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
    with ContextThreadPoolExecutor(max_workers=min(_MAX_NEWS_WORKERS, len(names))) as pool:
        batches = list(pool.map(_search_stock_news, names))
    records = [_strip_news_record(r) for r in _dedup_news(r for batch in batches for r in batch)]

    model_name = "deepseek-chat"
    model = get_deepseek(model=model_name, temperature=0.2)
    prompt = _build_news_prompt(current_time, " ".join(names), profiles)
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
