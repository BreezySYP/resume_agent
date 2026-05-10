"""
rag/vector_store.py
Redis Vector Store 的创建、连接与单例管理。
"""
from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores.redis import Redis as RedisVectorStore

from config.settings import OLLAMA_URL, EMBED_MODEL, REDIS_URL, VS_INDEX_NAME

# Embedding 模型（全局复用）
embeddings = OllamaEmbeddings(
    model=EMBED_MODEL,
    base_url=OLLAMA_URL,
)


@lru_cache(maxsize=1)
def get_vector_store() -> RedisVectorStore:
    """
    返回 Redis Vector Store 单例。
    首次调用时自动判断：已有 index → 直接连接；否则创建新 index。
    """
    try:
        vs = RedisVectorStore.from_existing_index(
            embedding=embeddings,
            index_name=VS_INDEX_NAME,
            redis_url=REDIS_URL,
        )
        print(f"✅ 连接已有 Vector Store: {VS_INDEX_NAME}")
        return vs
    except Exception:
        vs = RedisVectorStore.from_texts(
            texts=["__init__"],
            embedding=embeddings,
            index_name=VS_INDEX_NAME,
            redis_url=REDIS_URL,
        )
        print(f"✅ 创建新 Vector Store: {VS_INDEX_NAME}")
        return vs
