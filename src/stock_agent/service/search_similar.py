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
) -> pd.DataFrame:
    """混合召回 -> rerank -> top_k"""
    results = search_hybrid_join(collection, table, query, top_k=recall_k, group_key=group_key)
    if results.empty:
        return results
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
        "兆易创新（603986）股价从2026年6月29日高点846.66元跌至8月24日381.66元，跌幅超53%", "stock_news_hybrid", "stock_news", build_stock_news_text, 20
    )
    logger.success("finish search")
    logger.info(df["content"].iloc[0])
