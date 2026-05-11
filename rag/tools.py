"""
rag/tools.py
供 Agent 使用的三个工具：
  - rag_search      : 先查本地 Vector Store
  - tavily_search   : 实时搜索并自动缓存结果
  - analyze_code    : 代码质量分析
"""
import hashlib

from langchain_core.tools import tool
from langchain_core.documents import Document
from langchain_tavily import TavilySearch
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama

from config.settings import OLLAMA_URL, LLM_MODEL
from config.tracing import tracer
from rag.vector_store import get_vector_store

# ── 内部 LLM（analyze_code 专用，不对外暴露）────────────────────────────────
_llm = ChatOllama(
    model=LLM_MODEL,
    temperature=0.2,
    num_ctx=8192,
    num_gpu=999,
    base_url=OLLAMA_URL,
)

_tavily_raw = TavilySearch(max_results=5, search_depth="advanced", include_answer=True)
_splitter   = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)


def _tavily_cache_key(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()[:16]


def _cache_tavily_results(query: str, results: list[dict]) -> None:
    """把 Tavily 结果片段存入 Vector Store，供后续 rag_search 命中。"""
    docs = []
    for r in results:
        content = r.get("content", "") or r.get("answer", "")
        if not content:
            continue
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source_type": "tavily_cache",
                    "url":         r.get("url", ""),
                    "query":       query,
                    "cache_key":   _tavily_cache_key(query),
                },
            )
        )
    chunks = _splitter.split_documents(docs)
    if chunks:
        get_vector_store().add_documents(chunks)
        print(f"  💾 Tavily 缓存: {len(chunks)} chunks")


# ── 工具 ─────────────────────────────────────────────────────────────────────

@tool
def rag_search(query: str) -> str:
    """
    优先从本地知识库（Redis Vector Store）检索相关内容。
    包含已缓存的 Tavily 结果 + 本地 ingest 的文件。
    返回最相关的 3 条片段；未命中时建议调用 tavily_search。
    """
    with tracer.start_as_current_span("rag_search"):
        docs = get_vector_store().similarity_search(query, k=3)
        docs = [d for d in docs if d.page_content != "__init__"]
        if not docs:
            return "【RAG】知识库暂无相关内容，建议调用 tavily_search 获取最新信息。"
        parts = []
        for i, d in enumerate(docs, 1):
            src = d.metadata.get("file_name") or d.metadata.get("url") or "未知来源"
            parts.append(f"[{i}] 来源: {src}\n{d.page_content}")
        return "\n\n---\n\n".join(parts)


@tool
def tavily_search(query: str) -> str:
    """
    实时网络搜索（Tavily），并将结果自动缓存进 Vector Store 供后续复用。
    当 rag_search 内容不足或需要最新信息时使用。
    """
    with tracer.start_as_current_span("tavily_search"):
        raw = _tavily_raw.invoke(query)
        if isinstance(raw, list):
            _cache_tavily_results(query, raw)
            parts = [
                f"[{r.get('url', '')}]\n{r.get('content') or r.get('answer') or ''}"
                for r in raw
                if r.get("content") or r.get("answer")
            ]
            return "\n\n---\n\n".join(parts) or "未搜索到结果。"
        return str(raw)


@tool
def analyze_code(code: str) -> str:
    """分析代码质量、潜在 bug 和改进建议。"""
    with tracer.start_as_current_span("analyze_code"):
        return str(_llm.invoke(
            f"请分析以下代码的质量、潜在问题和改进建议：\n\n{code}"
        ).content)


# ── 各 Agent 工具集（供 agents/ 直接 import）────────────────────────────────
researcher_tools = [rag_search, tavily_search]
coder_tools      = [rag_search, analyze_code]
reviewer_tools   = [analyze_code]
