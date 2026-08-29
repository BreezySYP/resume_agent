"""storage/qdrant_writer.py — DataFrame -> Qdrant 向量写入（dense / dense+sparse hybrid）"""

import time
import uuid

import pandas as pd
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, PointStruct, SparseVector

from shared.db.qdrant import ensure_dense_collection, ensure_hybrid_collection, get_qdrant_client
from shared.models.ollama_models import get_embedding_dim, get_ollama_embedding
from shared.models.sparse import get_sparse_model

# bge-m3 最大上下文 8192 tokens。中文约 1 token/字，但数字/URL 等 ASCII 内容
# 可能 1 字符对应多个 token（实测 5288 字符的新闻文本也会超限）。
# 因此固定字符上限不够，整批失败时按预算逐级截断重试。
MAX_EMBED_TEXT_CHARS = 6000
EMBED_CHAR_BUDGETS = (MAX_EMBED_TEXT_CHARS, 3000, 1500, 800, 400)
_CONTEXT_LEN_HINT = "input length exceeds the context length"
_CHUNK_ID_NAMESPACE = uuid.NAMESPACE_URL


def _chunk_text(text: str, chunk_size: int, overlap: int = 200) -> list[str]:
    """按字符把长文本切成 ≤chunk_size 的块，相邻块保留 overlap 重叠，尽量在换行处断开。"""
    if not text or len(text) <= chunk_size:
        return [text]
    step = max(1, chunk_size - overlap)
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            nl = text.rfind("\n", start + chunk_size // 2, end)
            if nl > start:
                end = nl + 1
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(start + step, end - overlap)
        if start >= end:
            start = end
    return chunks


def _prepare_batch(
    batch_df: pd.DataFrame,
    build_text,
    get_payload,
    chunk_size: int = 0,
    chunk_overlap: int = 200,
) -> tuple[list[str], list, list[dict], list[int], list[str]]:
    """把一批行展开成待嵌入文本 / 点 id / payload，并返回需要清理的旧点。

    chunk_size>0 时一篇文章切成多块：点 id 用确定性 UUID（Qdrant 只接受整数或 UUID），
    payload 额外带 article_id / chunk_index；stale_ids 是历史文章级点的 id，
    article_ids 用于按 payload 清理旧 chunk。
    """
    texts, point_ids, payloads = [], [], []
    stale_ids, article_ids = [], []
    for _, row in batch_df.iterrows():
        full_text = build_text(row)
        if chunk_size > 0:
            chunks = _chunk_text(full_text, chunk_size, chunk_overlap)
            aid = str(row["id"])
            stale_ids.append(int(row["id"]))
            article_ids.append(aid)
        else:
            chunks = [full_text]
        base_payload = get_payload(row)
        for i, text in enumerate(chunks):
            texts.append(text)
            payload = dict(base_payload)
            if chunk_size > 0:
                point_ids.append(str(uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{aid}:{i}")))
                payload["article_id"] = aid
                payload["chunk_index"] = i
            else:
                point_ids.append(row["id"])
            payloads.append(payload)
    return texts, point_ids, payloads, stale_ids, article_ids


def _delete_stale_points(client: QdrantClient, collection: str, stale_ids: list[int], article_ids: list[str]) -> None:
    """先清理同一批文章在 Qdrant 里的旧向量：历史文章级点（id=文章id）+ 旧 chunk 点。"""
    if stale_ids:
        client.delete(collection_name=collection, points_selector=list(stale_ids))
    if article_ids:
        client.delete(
            collection_name=collection,
            points_selector=Filter(must=[FieldCondition(key="article_id", match=MatchAny(any=article_ids))]),
        )

def _fit_embed_texts(texts: list[str], max_chars: int = MAX_EMBED_TEXT_CHARS) -> list[str]:
    """把超长文本截断到 max_chars（保留开头，标题/导语权重最高）。"""
    fitted = []
    for text in texts:
        if isinstance(text, str) and len(text) > max_chars:
            logger.warning(
                "truncate embedding text {} chars -> {} chars",
                len(text),
                max_chars,
            )
            fitted.append(text[:max_chars])
        else:
            fitted.append(text)
    return fitted


def _embed_single_with_budget(model, text: str) -> list[float]:
    """单条嵌入；context 超长时按字符预算逐级截断重试，其他错误直接抛出。"""
    if not isinstance(text, str):
        return model([text])[0]
    sizes = {b for b in EMBED_CHAR_BUDGETS if b < len(text)}
    if len(text) <= MAX_EMBED_TEXT_CHARS:
        sizes.add(len(text))
    if not sizes:
        return model([text])[0]
    last_exc = None
    for size in sorted(sizes, reverse=True):
        cand = text if size == len(text) else text[:size]
        try:
            return model([cand])[0]
        except Exception as e:
            last_exc = e
            if _CONTEXT_LEN_HINT not in str(e):
                raise
            logger.warning("embedding text too long, retry with {} chars: {}", size, e)
    raise last_exc


def _embed_with_adaptive_truncation(model, texts: list[str]) -> list[list[float]]:
    """整批 embedding 因单条超长失败时，逐条嵌入并只对超长文本降级截断。"""
    return [_embed_single_with_budget(model, t) for t in texts]


def _embed_with_retry(model, texts: list[str], retries: int = 3, backoff: float = 1.0) -> list[list[float]]:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return model(_fit_embed_texts(texts))
        except Exception as e:
            last_exc = e
            if _CONTEXT_LEN_HINT in str(e):
                logger.error(
                    "embed_documents context length exceeded (attempt {}/{}): {}, fall back to per-text truncation",
                    attempt,
                    retries,
                    e,
                )
                return _embed_with_adaptive_truncation(model, _fit_embed_texts(texts))
            logger.error("embed_documents failed (attempt {}/{}): {}", attempt, retries, e)
            if attempt < retries:
                time.sleep(backoff * (2 ** (attempt - 1)))
    raise last_exc


def upsert_dense(df: pd.DataFrame, collection: str, build_text, get_payload, batch_size: int = 256, client: QdrantClient | None = None) -> None:
    client = client or get_qdrant_client()
    model = get_ollama_embedding()
    ensure_dense_collection(client, collection, get_embedding_dim())

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts = [build_text(row) for _, row in batch_df.iterrows()]
        vectors = _embed_with_retry(model, texts)
        points = [PointStruct(id=row["id"], vector=vector, payload=get_payload(row)) for (_, row), vector in zip(batch_df.iterrows(), vectors)]
        client.upsert(collection_name=collection, points=points, wait=False)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)


def upsert_hybrid(
    df: pd.DataFrame,
    collection: str,
    build_text,
    get_payload,
    batch_size: int = 256,
    client: QdrantClient | None = None,
    *,
    chunk_size: int = 0,
    chunk_overlap: int = 200,
) -> None:
    """dense (ollama embedding) + sparse (BM25) 混合向量写入。

    chunk_size>0 时对文本切块：一篇新闻 = 多个 chunk 点（payload 带 article_id/chunk_index），
    写入前清理该文章旧的向量点，搜索侧再按 article_id 聚合回文章级。
    """
    client = client or get_qdrant_client()
    model = get_ollama_embedding()
    sparse_model = get_sparse_model()
    ensure_hybrid_collection(client, collection, get_embedding_dim())

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts, point_ids, payloads, stale_ids, article_ids = _prepare_batch(
            batch_df, build_text, get_payload, chunk_size, chunk_overlap
        )
        dense_vectors = _embed_with_retry(model, texts)
        points = []
        for text_, dense_vec, point_id, payload in zip(texts, dense_vectors, point_ids, payloads):
            sparse_emb = next(iter(sparse_model.embed(text_)))
            sparse_vec = SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
            points.append(PointStruct(id=point_id, vector={"dense": dense_vec, "sparse": sparse_vec}, payload=payload))
        if chunk_size > 0:
            _delete_stale_points(client, collection, stale_ids, article_ids)
        client.upsert(collection_name=collection, points=points, wait=chunk_size > 0)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)
