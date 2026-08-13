"""storage/qdrant_writer.py — DataFrame -> Qdrant 向量写入（dense / dense+sparse hybrid）"""
from functools import lru_cache

import pandas as pd
from fastembed import SparseTextEmbedding
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector
from shared.db.qdrant import ensure_dense_collection, ensure_hybrid_collection, get_qdrant_client
from shared.models.ollama_models import get_ollama_embedding, get_embedding_dim, get_sparse_model
import time


def upsert_dense(df: pd.DataFrame, collection: str, build_text, get_payload, batch_size: int = 256, client: QdrantClient | None = None) -> None:
    client = client or get_qdrant_client()
    model = get_ollama_embedding()
    ensure_dense_collection(client, collection, get_embedding_dim())

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts = [build_text(row) for _, row in batch_df.iterrows()]
        vectors = model(texts)
        points = [PointStruct(id=row["id"], vector=vector, payload=get_payload(row)) for (_, row), vector in zip(batch_df.iterrows(), vectors)]
        client.upsert(collection_name=collection, points=points, wait=False)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)


def upsert_hybrid(df: pd.DataFrame, collection: str, build_text, get_payload, batch_size: int = 256, client: QdrantClient | None = None) -> None:
    """dense (ollama embedding) + sparse (BM25) 混合向量写入"""
    client = client or get_qdrant_client()
    model = get_ollama_embedding()
    sparse_model = get_sparse_model()
    ensure_hybrid_collection(client, collection, get_embedding_dim())

    total = len(df)
    logger.info("start embedding/upsert, rows={}", total)
    def _embed_with_retry(model, texts, retries: int = 3, backoff: float = 1.0):
        for attempt in range(retries):
            try:
                return model(texts)
            except Exception as e:
                logger.error("embed_documents failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
                    continue
                raise

    for start in range(0, total, batch_size):
        batch_df = df.iloc[start:start + batch_size]
        texts = [build_text(row) for _, row in batch_df.iterrows()]
        dense_vectors = _embed_with_retry(model, texts)
        points = []
        for (_, row), text_, dense_vec in zip(batch_df.iterrows(), texts, dense_vectors):
            sparse_emb = next(iter(sparse_model.embed(text_)))
            sparse_vec = SparseVector(indices=sparse_emb.indices.tolist(), values=sparse_emb.values.tolist())
            points.append(PointStruct(id=row["id"], vector={"dense": dense_vec, "sparse": sparse_vec}, payload=get_payload(row)))
        client.upsert(collection_name=collection, points=points, wait=False)
        logger.info("upserted {}/{}", min(start + batch_size, total), total)
    logger.success("finished. total={}", total)
