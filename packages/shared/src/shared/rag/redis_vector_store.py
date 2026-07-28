# shared/rag/redis_vector_store.py
import logging
from functools import lru_cache
from typing import List, Dict, Optional

from langchain_redis import RedisVectorStore

from shared.models.ollama_models import get_embedding
from shared.configs.settings import REDIS_URL

logger = logging.getLogger(__name__)

class VectorStoreService:
    """向量存储服务 - 极简版"""
    
    def __init__(self, embedding=None):
        self.embedding = embedding or get_embedding()
        self.index_name = "market_news_global_v1"
        self.redis_url =  REDIS_URL  # ← 根据你的实际 Redis 地址修改
    
    @lru_cache(maxsize=1)
    def get_store(self) -> RedisVectorStore:
        metadata_schema = [
            {"name": "unique_id", "type": "tag"},
            {"name": "code", "type": "tag"},
            {"name": "date", "type": "numeric"},      # 匹配你代码里的 date
            {"name": "mediaName", "type": "tag"},
        ]
        
        try:
            store = RedisVectorStore(
                embeddings=self.embedding,
                index_name=self.index_name,
                redis_url=self.redis_url,
                vector_schema={
                    "type": "HNSW",
                    "dims": 1024,
                    "distance_metric": "COSINE"
                },
                metadata_schema=metadata_schema,
            )
            logger.info(f"✅ Vector Store 初始化成功: {self.index_name}")
            return store
        except Exception as e:
            logger.error(f"VectorStore 初始化失败: {e}", exc_info=True)
            raise
    
    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: Optional[List[str]] = None):
        store = self.get_store()
        try:
            store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            logger.info(f"✅ 添加 {len(texts)} 条向量文档")
            return True
        except Exception as e:
            logger.error(f"向量添加失败: {e}", exc_info=True)
            return False