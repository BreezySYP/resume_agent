"""rag/vector_store.py — Redis Vector Store"""
from functools import lru_cache
from langchain_redis import RedisVectorStore
from shared.configs.settings import REDIS_URL, VS_INDEX_NAME
from shared.models.ollama import get_embedding


@lru_cache(maxsize=1)
def get_vector_store() -> RedisVectorStore:
    vs = RedisVectorStore.from_texts(
        texts=["__init__"],
        embedding=get_embedding(),
        index_name=VS_INDEX_NAME,
        redis_url=REDIS_URL,
    )
    print(f"✅ Vector Store 就绪: {VS_INDEX_NAME}")
    return vs


@lru_cache(maxsize=1)
def get_vector_store(index_name) -> RedisVectorStore:
    vs = RedisVectorStore.from_texts(
        texts=["__init__"],
        embedding=get_embedding(),
        index_name=index_name,
        redis_url=REDIS_URL,
    )
    print(f"✅ Vector Store 就绪: {index_name}")
    return vs