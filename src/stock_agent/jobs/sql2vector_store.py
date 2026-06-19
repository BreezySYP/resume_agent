import hashlib
import uuid

import pandas as pd
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    SparseVector,
    VectorParams,
    PointStruct,
    SparseVectorParams
)
from fastembed import SparseTextEmbedding

from data.text_helper import build_stock_news_text, build_stock_profile_text, get_stock_news_payload, get_stock_profile_payload
from jobs.data_loader import load_df
from shared.models.ollama import get_embedding, get_embedding_dim

QDRANT_NEWS_COLLECTION = "stock_news"
QDRANT_BUSINESS_BREAKDOWN_COLLECTION = "stock_business_breakdown"
QDRANT_PROFILE_COLLECTION = "stock_profile"

model = get_embedding()


# def make_qdrant_id(row) -> str:
#     """
#     同一股票同一标题同一天视为同一条新闻
#     """
#     raw = f"{row['code']}|{row['title']}|{row['date']}"
#     md5_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()
#     return str(uuid.UUID(md5_hex))



def get_qdrant_client() -> QdrantClient:
    client = QdrantClient(
        host="host.docker.internal",
        port=6333,
    )
    return client

def create_collection(dim, collection=QDRANT_NEWS_COLLECTION):
    if not client.collection_exists(collection):
        logger.info( f"create collection={collection}, dim={dim}")
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=dim,
                distance=Distance.COSINE,
            ),
        )

    else:
        info = client.get_collection(collection)
        current_dim = (info.config.params.vectors.size)
        if current_dim != dim:
            raise RuntimeError(
                f"Collection dim mismatch. "
                f"collection={current_dim}, "
                f"embedding={dim}. "
                f"请删除旧 collection 后重建。"
            )
        

def create_collection_hybrid(dim, collection=QDRANT_PROFILE_COLLECTION):
    logger.info( f"create collection={collection}, dim={dim}")
    client.create_collection(
        collection_name=collection,
        vectors_config={
        "dense": VectorParams(     # 保留你的 nomic 维度
            size=get_embedding_dim(),                     # nomic-embed-text 是 768
            distance=Distance.COSINE,
        )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                modifier=Modifier.IDF   # 提升稀有词（如“液冷”）权重
            )
        }
    )



def upsert_qdrant(df: pd.DataFrame,client: QdrantClient, build_text, get_payload, collection_name, batch_size: int = 512):
    total = len(df)
    logger.info(f"start embedding/upsert, rows={total}")

    for start in range(0, total, batch_size):

        batch_df = df.iloc[start:start + batch_size]

        texts = [
            build_text(row)
            for _, row in batch_df.iterrows()
        ]

        vectors = model.embed_documents(texts)

        points = []

        for (_, row), vector in zip(batch_df.iterrows(),vectors,):

            # qdrant_id = make_qdrant_id(row)

            payload = get_payload(row)

            points.append(
                PointStruct(
                    id=row["id"],
                    vector=vector,
                    payload=payload,
                )
            )

        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=False,
        )

        logger.info( f"upserted {min(start+batch_size,total)}/{total}")

    logger.success(f"finished. total={total}")

sparse_model = SparseTextEmbedding("Qdrant/bm25")

def upsert_qdrant_v2(df: pd.DataFrame,client: QdrantClient, build_text, get_payload, collection_name, batch_size: int = 512):
    total = len(df)
    logger.info(f"start embedding/upsert, rows={total}")

    for start in range(0, total, batch_size):

        batch_df = df.iloc[start:start + batch_size]

        texts = [
            build_text(row)
            for _, row in batch_df.iterrows()
        ]

        vectors = model.embed_documents(texts)
        points = []

        for (_, row), vector in zip(batch_df.iterrows(),vectors,):

            # qdrant_id = make_qdrant_id(row)
            t = build_text(row)
            sparse_embedding = list(sparse_model.embed(t))[0]

            sparse_vec = SparseVector(
                indices=sparse_embedding.indices.tolist(),   # 或 .tolist() 如果已经是 array
                values=sparse_embedding.values.tolist()
            )
            payload = get_payload(row)

            points.append(
                PointStruct(
                    id=row["id"],
                    vector={
                        "dense": vector,           # 直接用旧的 nomic 向量
                        "sparse": sparse_vec
                    },
                    payload=payload,
                )
            )

        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=False,
        )

        logger.info( f"upserted {min(start+batch_size,total)}/{total}")

    logger.success(f"finished. total={total}")
# def v2v_migrate(collection_old, collection_new, build_text):
#     sparse_model = SparseTextEmbedding("Qdrant/bm25")   # 非常轻量

#     # 假设你能从旧 collection 批量读数据
#     scroll_id = None
#     batch_size = 500   # 根据内存调整，100万数据建议分批

#     while True:
#         scroll_result = client.scroll(
#             collection_name=collection_old,  # 改成你现在的
#             limit=batch_size,
#             offset=scroll_id,
#             with_payload=True,
#             with_vectors=True   # 取出已有的 dense 向量
#         )
        
#         points = []
#         for point in scroll_result[0]:
#             company = point.payload
#             text = build_text(company)
            
#             # 只生成 sparse（dense 直接复用原来的）
#             sparse_vec = list(sparse_model.embed(text))[0]
            
#             points.append(PointStruct(
#                 id=point.id,
#                 vector={
#                     "dense": point.vector,           # 直接用旧的 nomic 向量
#                     "sparse": sparse_vec
#                 },
#                 payload=company
#             ))
        
#         if points:
#             client.upsert(
#                 collection_name=collection_new,
#                 points=points,
#                 wait=False   # 异步加快速度
#             )
        
#         scroll_id = scroll_result[1]
#         if scroll_id is None:
#             break
        
#         print(f"已迁移 {len(points)} 条...")


if __name__ == "__main__":
    
    client = get_qdrant_client()
    dim = get_embedding_dim()

    # client.delete_collection(QDRANT_PROFILE_COLLECTION)

    create_collection_hybrid(dim, "stock_news_hybrid")
    df = load_df("SELECT * FROM mydb.stock_news", "stock_news")
    upsert_qdrant_v2(df, client, build_stock_news_text, get_stock_news_payload, "stock_news_hybrid", batch_size=128)
    
    # df = load_df("SELECT * FROM mydb.stock_business_breakdown", "stock_business_breakdown")
    # create_collection(dim, QDRANT_BUSINESS_BREAKDOWN_COLLECTION)
    # upsert_qdrant(df, client, build_business_breakdown_text, get_business_breakdown_payload, QDRANT_BUSINESS_BREAKDOWN_COLLECTION, batch_size=128)
    
    # df = load_df("SELECT * FROM mydb.stock_profile", "stock_profile")
    # create_collection(dim, "stock_profile_hybrid")
    # upsert_qdrant(df, client, build_stock_profile_text, get_stock_profile_payload, QDRANT_PROFILE_COLLECTION, batch_size=128)
    # create_collection_hybrid(dim, "stock_profile_hybrid")
    # upsert_qdrant_v2(df, client, build_stock_profile_text, get_stock_profile_payload, "stock_profile_hybrid", batch_size=128)



