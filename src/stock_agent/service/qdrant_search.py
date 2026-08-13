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


def search_dense(
    collection: str,
    query: str,
    top_k: int = 5,
    *,
    using: str = "dense",
    query_filter: Optional[models.Filter] = None,
    with_payload: bool = True,
) -> pd.DataFrame:
    qvec = get_embedding().embed_query(query)
    hits = get_qdrant_client().query_points(
        collection_name=collection,
        query=qvec,
        using=using,
        query_filter=query_filter,
        limit=top_k,
        with_payload=with_payload,
    )
    return _hits_to_df(hits.model_dump()["points"])


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
) -> pd.DataFrame:
    dense_query = get_embedding().embed_query(query)
    sparse_vec = embed_sparse(query)

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
        limit=top_k,
        with_payload=with_payload,
    )
    return _hits_to_df(results.model_dump()["points"])


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