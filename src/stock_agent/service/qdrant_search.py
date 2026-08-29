# packages/shared/search/qdrant_search.py
"""通用 Qdrant dense / hybrid 检索，业务侧只传 collection、filter、query"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from qdrant_client import models
from qdrant_client.models import Prefetch
from shared.db.qdrant import get_qdrant_client
from shared.models.ollama_models import get_embedding
from shared.models.sparse import embed_sparse


def _hits_to_df(points: list[dict]) -> pd.DataFrame:
    if not points:
        return pd.DataFrame(columns=["id", "score", "payload"])
    return pd.DataFrame(
        [{"id": h["id"], "score": h["score"], "payload": h.get("payload")} for h in points]
    )


def _aggregate_by_group_key(hits: pd.DataFrame, group_key: str) -> pd.DataFrame:
    """chunk 化集合按文章聚合：每篇保留最高分块，返回 id 改为 article_id。

    兼容迁移期：旧样式点没有 group_key 字段时退回点 id，仍按文章聚合。
    """
    if hits.empty:
        return hits
    hits = hits.copy()

    def article_id_of(row) -> str:
        payload = row["payload"] if isinstance(row["payload"], dict) else {}
        return str(payload.get(group_key, row["id"]))

    hits["_article_id"] = hits.apply(article_id_of, axis=1)
    best = hits.sort_values("score", ascending=False).drop_duplicates("_article_id", keep="first")
    best["id"] = best["_article_id"]
    return best.drop(columns=["_article_id"]).reset_index(drop=True)


def search_dense(
    collection: str,
    query: str,
    top_k: int = 5,
    *,
    using: str = "dense",
    query_filter: Optional[models.Filter] = None,
    with_payload: bool = True,
    group_key: Optional[str] = None,
    chunk_multiplier: int = 4,
) -> pd.DataFrame:
    qvec = get_embedding().embed_query(query)
    limit = top_k * chunk_multiplier if group_key else top_k
    hits = get_qdrant_client().query_points(
        collection_name=collection,
        query=qvec,
        using=using,
        query_filter=query_filter,
        limit=limit,
        with_payload=with_payload,
    )
    df = _hits_to_df(hits.model_dump()["points"])
    if group_key:
        df = _aggregate_by_group_key(df, group_key)
    return df


def search_hybrid(
    collection: str,
    query: str,
    top_k: int = 5,
    *,
    dense_using: str = "dense",
    sparse_using: str = "sparse",
    prefetch_limit: int = 30,
    query_filter: Optional[models.Filter] = None,
    with_payload: bool = True,
    group_key: Optional[str] = None,
    chunk_multiplier: int = 4,
) -> pd.DataFrame:
    dense_query = get_embedding().embed_query(query)
    sparse_vec = embed_sparse(query)

    limit = top_k
    if group_key:
        # chunk 化集合里先多召回几倍块，聚合后才能凑够 top_k 篇文章
        limit = top_k * chunk_multiplier
        prefetch_limit = max(prefetch_limit, limit)

    results = get_qdrant_client().query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(
                query=dense_query,
                using=dense_using,
                limit=prefetch_limit,
                filter=query_filter,
            ),
            Prefetch(
                query=sparse_vec,
                using=sparse_using,
                limit=prefetch_limit,
                filter=query_filter,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=with_payload,
    )
    df = _hits_to_df(results.model_dump()["points"])
    if group_key:
        df = _aggregate_by_group_key(df, group_key)
    return df


def upsert_hybrid_point(
    collection: str,
    point_id: Any,
    text: str,
    payload: dict,
    *,
    dense_name: str = "dense",
    sparse_name: str = "sparse",
) -> None:
    """通用 hybrid point 写入（股票/记忆都可复用）"""
    dense = get_embedding().embed_query(text)
    sparse_vec = embed_sparse(text)
    get_qdrant_client().upsert(
        collection_name=collection,
        points=[
            models.PointStruct(
                id=point_id,
                vector={dense_name: dense, sparse_name: sparse_vec},
                payload=payload,
            )
        ],
    )
