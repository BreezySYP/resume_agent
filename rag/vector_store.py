"""
rag/vector_store.py
Redis Vector Store - 使用 langchain-redis 默认 schema，避免字段名冲突。
"""
from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from langchain_redis import RedisVectorStore

from config.settings import OLLAMA_URL, EMBED_MODEL, REDIS_URL, VS_INDEX_NAME

embeddings = OllamaEmbeddings(
    model=EMBED_MODEL,
    base_url=OLLAMA_URL,
)


@lru_cache(maxsize=1)
def get_vector_store() -> RedisVectorStore:
    """
    使用 langchain-redis 默认 schema 创建/复用 Vector Store。
    不手动定义 schema，让库自己管理字段名，避免版本兼容问题。
    """
    vs = RedisVectorStore.from_texts(
        texts=["__init__"],
        embedding=embeddings,
        index_name=VS_INDEX_NAME,
        redis_url=REDIS_URL,
    )
    print(f"✅ Vector Store 就绪: {VS_INDEX_NAME}")
    return vs


def verify():
    vs = get_vector_store()
    results = vs.similarity_search('developer experience', k=3)
    for doc in results:
        print('---')
        print(doc.metadata)
        print(doc.page_content[:100])

if __name__ == "__main__":
    verify()