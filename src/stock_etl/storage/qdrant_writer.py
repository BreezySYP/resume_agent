"""storage/qdrant_writer.py — DataFrame -> Qdrant 向量写入（dense / dense+sparse hybrid）"""
from functools import lru_cache

import pandas as pd
from fastembed import SparseTextEmbedding
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from shared.db.qdrant import ensure_dense_collection, ensure_hybrid_collection, get_qdrant_client
from shared.models.ollama import get_embedding, get_embedding_dim


@lru_cache(maxsize=1)
def _sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding("Qdrant/bm25")


def upsert_dense(df: pd.DataFrame, collection: str, build_text, get_payload, batch_size: int = 512, client: QdrantClient | None = None) -> None:
    client = client or get_qdrant_client()
    model = get_embedding()
    ensure_dense_collection(client, collection, get_embedding_dim(model))

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts = [build_text(row) for _, row in batch_df.iterrows()]
        vectors = model.embed_documents(texts)
        points = [PointStruct(id=row["id"], vector=vector, payload=get_payload(row)) for (_, row), vector in zip(batch_df.iterrows(), vectors)]
        client.upsert(collection_name=collection, points=points, wait=False)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)


def upsert_hybrid(df: pd.DataFrame, collection: str, build_text, get_payload, batch_size: int = 512, client: QdrantClient | None = None) -> None:
    """dense (ollama embedding) + sparse (BM25) 混合向量写入"""
    client = client or get_qdrant_client()
    model = get_embedding()
    sparse_model = _sparse_model()
    ensure_hybrid_collection(client, collection, get_embedding_dim(model))

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts = [build_text(row) for _, row in batch_df.iterrows()]
        dense_vectors = model.embed_documents(texts)
        points = []
        for (_, row), text_, dense_vec in zip(batch_df.iterrows(), texts, dense_vectors):
            sparse_emb = next(iter(sparse_model.embed(text_)))
            sparse_vec = SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
            points.append(PointStruct(id=row["id"], vector={"dense": dense_vec, "sparse": sparse_vec}, payload=get_payload(row)))
        client.upsert(collection_name=collection, points=points, wait=False)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)
