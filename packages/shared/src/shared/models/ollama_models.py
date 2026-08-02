"""shared/models/ollama.py — LLM + Embedding 单例，所有服务共用"""
from functools import lru_cache
from typing import List
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_groq import ChatGroq
from shared.configs.settings import OLLAMA_URL, LLM_MODEL, LLM_SQL, EMBED_MODEL, GROQ_API_KEY
from loguru import logger


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    logger.info("preparing llm...")
    llm = ChatOllama(model=LLM_MODEL, 
                     temperature=0,
                    #   num_ctx=8192, 
                    #   num_gpu=999, 
                      base_url=OLLAMA_URL)
    logger.info("✅ llm ready")
    return llm


@lru_cache(maxsize=1)
def get_llm_sql() -> ChatOllama:
    """专门用于 SQL 生成（qwen2.5-coder），temperature=0 确保确定性输出"""
    return ChatOllama(model=LLM_SQL, temperature=0, base_url=OLLAMA_URL)


@lru_cache(maxsize=1)
def get_fast_llm():
    """Groq 快速推理用于 Supervisor/Review 等轻量节点；无 key 时 fallback Ollama"""
    if GROQ_API_KEY:
        return ChatGroq(model="llama3-70b-8192", temperature=0.2, api_key=GROQ_API_KEY)
    return get_llm()


@lru_cache(maxsize=1)
def get_embedding() -> OllamaEmbeddings:
    logger.info("preparing embeddings...")
    emb = OllamaEmbeddings(model=EMBED_MODEL, num_gpu=2, base_url=OLLAMA_URL)
    logger.info("✅ embeddings ready")
    return emb

def get_embedding_dim():
    vec = get_ollama_embedding()(["test"])
    return len(vec[0])


    
@lru_cache(maxsize=1)
def get_ollama_embedding():
    import ollama
    logger.info(f"preparing embeddings with native ollama (bge-m3) @ {OLLAMA_URL}...")
    
    # 配置 client
    client = ollama.Client(host=OLLAMA_URL)
    
    def embed_documents(texts: List[str]):
        
        response = client.embed(
            model=EMBED_MODEL,   # "bge-m3"
            input=texts
        )
        return response['embeddings']
    
    logger.info("✅ ollama native client ready")
    return embed_documents
    


if __name__ == "__main__":
    # print(get_embedding_dim()) 
    print(len(get_ollama_embedding()(["Hello world", "This is a test"])[0])) 