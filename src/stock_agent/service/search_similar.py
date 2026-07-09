"""service/search_similar.py — Qdrant 混合检索 + MySQL 回表 + rerank"""
from functools import lru_cache

import pandas as pd
from fastembed import SparseTextEmbedding
from loguru import logger
from qdrant_client import models
from qdrant_client.models import Prefetch, SparseVector
from shared.db.mysql import engine
from shared.db.qdrant import get_qdrant_client
from shared.models.ollama_models import get_embedding 
from service.cuda_service import rerank


@lru_cache(maxsize=1)
def get_sparse_model():
    return SparseTextEmbedding("Qdrant/bm25")

def search_from_qdrant(collection: str, query: str, top_k: int = 5) -> pd.DataFrame:
    qvec = get_embedding().embed_query(query)
    hits = get_qdrant_client().query_points(collection_name=collection, query=qvec, limit=top_k)
    return pd.DataFrame([{"id": h["id"], "score": h["score"], "payload": h["payload"]} for h in hits.dict()["points"]])


def search_from_qdrant_hybrid(collection: str, query: str, top_k: int = 5) -> pd.DataFrame:
    dense_query = get_embedding().embed_query(query)
    sparse_emb = next(iter(get_sparse_model().embed(query)))
    sparse_vec = SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
    results = get_qdrant_client().query_points(
        collection_name=collection,
        prefetch=[Prefetch(query=dense_query, using="dense", limit=30), Prefetch(query=sparse_vec, using="sparse", limit=30)],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return pd.DataFrame([{"id": h["id"], "score": h["score"], "payload": h["payload"]} for h in results.model_dump()["points"]])


def find_from_db_by_ids(table: str, ids: list) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {table} WHERE id in ({str(ids)[1:-1]})", con=engine.connect())


def search(collection: str, table: str, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_from_qdrant(collection, query, top_k)
    df = find_from_db_by_ids(table, list(hits["id"]))
    df["original_score"] = hits["score"]
    return df


def search_hybrid(collection: str, table: str, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_from_qdrant_hybrid(collection, query, top_k)
    df = find_from_db_by_ids(table, list(hits["id"]))
    df["original_score"] = hits["score"]
    return df


def search_with_rerank(query: str, collection: str, table: str, build_text, top_k: int = 5) -> pd.DataFrame:
    """混合召回 top 100 -> rerank -> 取最终 top_k"""
    results = search_hybrid(collection, table, query, top_k=100)
    scores = rerank(query=query, docs=[build_text(row) for _, row in results.iterrows()])
    results["rerank_score"] = scores["rerank_score"]
    return results.loc[results["rerank_score"].nlargest(top_k).index]


if __name__ == "__main__":
    from shared.text.stock_text import build_stock_profile_text

    logger.info("start search...")
    df = search_with_rerank("液冷服务器", "stock_profile_hybrid", "stock_profile", build_stock_profile_text, 20)
    logger.success("finish search")
    logger.info(df)
