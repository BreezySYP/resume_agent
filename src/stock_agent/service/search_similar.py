"""service/search_similar.py — 股票等业务检索：复用 shared.search + rerank"""
import pandas as pd
from loguru import logger
from service.cuda_service import rerank
from service.sql_helper import fetch_by_ids, attach_scores
from service.qdrant_search import search_dense, search_hybrid



def search_join(collection: str, table: str, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_dense(collection, query, top_k)
    df = fetch_by_ids(table, list(hits["id"]))
    return attach_scores(df, hits)


def search_hybrid_join(collection: str, table: str, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_hybrid(collection, query, top_k)
    df = fetch_by_ids(table, list(hits["id"]))
    return attach_scores(df, hits)


def search_with_rerank(
    query: str,
    collection: str,
    table: str,
    build_text,
    top_k: int = 5,
    recall_k: int = 100,
) -> pd.DataFrame:
    """混合召回 -> rerank -> top_k"""
    results = search_hybrid_join(collection, table, query, top_k=recall_k)
    if results.empty:
        return results
    scores = rerank(query=query, docs=[build_text(row) for _, row in results.iterrows()])
    results = results.copy()
    results["rerank_score"] = scores["rerank_score"]
    return results.loc[results["rerank_score"].nlargest(top_k).index]


if __name__ == "__main__":
    from shared.text.stock_text import build_stock_profile_text

    logger.info("start search...")
    df = search_with_rerank(
        "液冷服务器", "stock_profile_hybrid", "stock_profile", build_stock_profile_text, 20
    )
    logger.success("finish search")
    logger.info(df)