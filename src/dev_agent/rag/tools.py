"""rag/tools.py — Dev Agent 工具集"""
import hashlib
import os
from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_tavily import TavilySearch
from langchain_text_splitters import RecursiveCharacterTextSplitter
from shared.configs.settings import GRAPH_CONFIG
from shared.configs.tracing import tracer
from shared.models.ollama_models import get_llm
from rag.vector_store import get_vector_store
from langchain_core.messages import HumanMessage

_tavily_raw = TavilySearch(max_results=5, search_depth="advanced", include_answer=True)
_splitter   = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)


def _cache_tavily_results(query: str, results: list[dict]) -> None:
    docs = [
        Document(
            page_content=r.get("content", "") or r.get("answer", ""),
            metadata={"source_type": "tavily_cache", "url": r.get("url", ""), "query": query},
        )
        for r in results if r.get("content") or r.get("answer")
    ]
    chunks = _splitter.split_documents(docs)
    if chunks:
        get_vector_store().add_documents(chunks)
        print(f"  💾 Tavily 缓存: {len(chunks)} chunks")


@tool
def rag_search(query: str) -> str:
    """优先从本地知识库检索，未命中时建议调用 tavily_search。"""
    with tracer.start_as_current_span("rag_search"):
        docs = [d for d in get_vector_store().similarity_search(query, k=3)
                if d.page_content != "__init__"]
        if not docs:
            return "【RAG】知识库暂无相关内容，建议调用 tavily_search。"
        parts = [
            f"[{i}] 来源: {d.metadata.get('file_name') or d.metadata.get('url') or '未知'}\n{d.page_content}"
            for i, d in enumerate(docs, 1)
        ]
        return "\n\n---\n\n".join(parts)


@tool
def tavily_search(query: str) -> str:
    """实时网络搜索，结果自动缓存到 Vector Store。"""
    with tracer.start_as_current_span("tavily_search"):
        raw = _tavily_raw.invoke(query)
        if isinstance(raw, list):
            _cache_tavily_results(query, raw)
            parts = [
                f"[{r.get('url', '')}]\n{r.get('content') or r.get('answer') or ''}"
                for r in raw if r.get("content") or r.get("answer")
            ]
            return "\n\n---\n\n".join(parts) or "未搜索到结果。"
        return str(raw)


@tool
def analyze_code(code: str) -> str:
    """分析代码质量、潜在 bug 和改进建议。"""
    with tracer.start_as_current_span("analyze_code"):
        return str(get_llm().invoke(
            f"请分析以下代码的质量、潜在问题和改进建议：\n\n{code}"
        ).content)

from langgraph.pregel.remote import RemoteGraph
_stock_agent = RemoteGraph(
    "stock_agent",
    url=os.getenv("STOCK_AGENT_URL", "http://localhost:8002"),
)

@tool
def ask_stock_agent(question: str) -> str:
    """
    查询A股股票数据、历史价格、涨跌幅分析。
    输入自然语言问题，返回分析结果。
    """
    result = _stock_agent.invoke(
        {
            "messages":        [HumanMessage(content=question)],
            "user_question":   question,
            "retry_count":     0,
            "review_feedback": None,
        },
        config=GRAPH_CONFIG
    )
    return result.get("final_answer", result["messages"][-1].content)

researcher_tools = [rag_search, tavily_search, ask_stock_agent]
coder_tools      = [rag_search, analyze_code]
reviewer_tools   = [analyze_code]
