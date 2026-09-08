"""service/search_similar.py — 股票等业务检索：复用 shared.search + rerank"""
import pandas as pd
from loguru import logger
from service.cuda_service import rerank
from service.qdrant_search import search_dense, search_hybrid
from service.sql_helper import attach_scores, fetch_by_ids


def search_join(collection: str, table: str, query: str, top_k: int = 5, group_key: str | None = None) -> pd.DataFrame:
    hits = search_dense(collection, query, top_k, group_key=group_key)
    df = fetch_by_ids(table, list(hits["id"]))
    return attach_scores(df, hits)


def search_hybrid_join(collection: str, table: str, query: str, top_k: int = 5, group_key: str | None = None) -> pd.DataFrame:
    hits = search_hybrid(collection, query, top_k, group_key=group_key)
    df = fetch_by_ids(table, list(hits["id"]))
    return attach_scores(df, hits)


def search_with_rerank(
    query: str,
    collection: str,
    table: str,
    build_text,
    top_k: int = 5,
    recall_k: int = 100,
    group_key: str | None = None,
    rerank_cap: int = 50,
) -> pd.DataFrame:
    """混合召回 -> rerank -> top_k

    group_key 聚合可能返回数百条（chunk×4），全量 rerank 太慢，先按召回分
    截到 rerank_cap 条再 rerank。
    """
    results = search_hybrid_join(collection, table, query, top_k=recall_k, group_key=group_key)
    if results.empty:
        return results
    if rerank_cap and len(results) > rerank_cap:
        if "original_score" in results.columns:
            results = results.sort_values(
                "original_score", ascending=False, na_position="last"
            ).head(rerank_cap)
        else:
            results = results.head(rerank_cap)
    try:
        scores = rerank(query=query, docs=[build_text(row) for _, row in results.iterrows()])
    except Exception as e:
        # rerank 服务超时/不可用时降级为召回分排序，避免整个检索链路中断
        logger.warning("rerank failed, fallback to original_score: {}", e)
        return results.loc[results["original_score"].nlargest(top_k).index]
    results = results.copy()
    results["rerank_score"] = scores["rerank_score"]
    return results.loc[results["rerank_score"].nlargest(top_k).index]


if __name__ == "__main__":
    from shared.text.stock_text import build_stock_news_text

    logger.info("start search...")
    df = search_with_rerank(
        "影石创新", "stock_news_hybrid", "stock_news", build_stock_news_text, 20
    )
    logger.success("finish search")
    logger.info(df["content"].iloc[0])
