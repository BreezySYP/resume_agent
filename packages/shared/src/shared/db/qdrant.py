"""shared/db/qdrant.py — Qdrant client + collection 管理，ETL 写入与 Agent 检索共用"""
from functools import lru_cache

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Modifier, SparseVectorParams, VectorParams
from shared.configs.settings import QDRANT_URL


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def ensure_dense_collection(client: QdrantClient, collection: str, dim: int) -> None:
    """确保稠密向量 collection 存在，维度不匹配则报错提示重建"""
    if not client.collection_exists(collection):
        logger.info("create collection={}, dim={}", collection, dim)
        client.create_collection(collection_name=collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        return
    info = client.get_collection(collection)
    current_dim = info.config.params.vectors.size
    if current_dim != dim:
        raise RuntimeError(f"Collection dim mismatch. collection={current_dim}, embedding={dim}. 请删除旧 collection 后重建。")


def ensure_hybrid_collection(client: QdrantClient, collection: str, dim: int) -> None:
    """确保稠密 + 稀疏(BM25) 混合 collection 存在"""
    if client.collection_exists(collection):
        return
    logger.info("create hybrid collection={}, dim={}", collection, dim)
    client.create_collection(
        collection_name=collection,
        vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
    )
