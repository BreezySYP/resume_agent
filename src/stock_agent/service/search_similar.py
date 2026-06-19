import os

from fastembed import SparseTextEmbedding
from qdrant_client import models

from core.db import engine
import pandas as pd
from shared.models.ollama import get_embedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    SparseVector,
    VectorParams,
    PointStruct,
    SparseVectorParams,
    Prefetch
)
from loguru import logger

qdrant_url = os.getenv("QDRANT_URL")

client = QdrantClient(url=qdrant_url)
model = get_embedding()

def search_from_qdrant(collection, query: str, top_k: int = 5) -> pd.DataFrame:
    qvec = model.embed_query(query)

    hits = client.query_points(collection_name=collection, query=qvec, limit=top_k)

    return pd.DataFrame([
        {
            "id": h["id"],
            "score": h["score"],
            "payload": h["payload"]
        }
        for h in hits.dict()['points']
    ])


sparse_model = SparseTextEmbedding("Qdrant/bm25")

def search_from_qdrant_v2(collection, query: str, top_k: int = 5) -> pd.DataFrame:
    dense_query = model.embed_query(query)
    sparse_emb = list(sparse_model.embed(query))[0]
    sparse_vec = SparseVector(
        indices=sparse_emb.indices.tolist(),
        values=sparse_emb.values.tolist()
    )
    results = client.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(query=dense_query, using="dense", limit=30),
            Prefetch(query=sparse_vec, using="sparse", limit=30)
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True
    )
    return pd.DataFrame([
        {
            "id": h["id"],
            "score": h["score"],
            "payload": h["payload"]
        }
        for h in results.model_dump()['points']
    ])

def find_from_db_by_ids(table, ids) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM mydb.{table} WHERE id in ({str(ids)[1:-1]})", con=engine.connect())


def search(collection, table, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_from_qdrant(collection, query, top_k)
    ids = list(hits["id"])
    df = find_from_db_by_ids(table, ids)
    df["original_score"] = hits["score"]
    return df

def search_v2(collection, table_name, query: str, top_k: int = 5) -> pd.DataFrame:
    hits = search_from_qdrant_v2(collection, query, top_k)
    ids = list(hits["id"])
    df = find_from_db_by_ids(table_name, ids)
    df["original_score"] = hits["score"]
    return df


def search_v3(query, collection, table_name, build_text, top_k=5):
    from service.cuda_service import rerank

    results = search_v2( collection=collection, table_name=table_name, query=query, top_k=100)
    # pairs = [(query,  build_stock_news_text(r)) for r in results]
    scores = rerank(query=query, docs=[build_text(d) for _, d in results.iterrows()])

    # scores["original_score"] = results["original_score"]
    results["rerank_score"] = scores["rerank_score"]
    return  results.loc[results['rerank_score'].nlargest(top_k).index]
    

if __name__ == "__main__":
    # res = search_v2("stock_profile_hybrid", "stock_profile", "人工智能")
    # res = search("stock_news", "算电协同")
    # for r in res:
    #     print(r)
    from data.text_helper import build_stock_profile_text
    logger.info("start search : ")
    df = search_v3("液冷服务器", "stock_profile_hybrid", "stock_profile", build_stock_profile_text, 20)
    logger.success("finish search")
    logger.info(df)
    # df.to_csv("./src/stock_agent/service/data/search_fimilar.csv")
    # logger.success("result saved at ./src/stock_agent/service/data/search_fimilar.csv")
