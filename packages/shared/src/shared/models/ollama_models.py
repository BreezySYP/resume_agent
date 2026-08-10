"""shared/models/ollama.py — LLM + Embedding 单例，所有服务共用"""
from functools import lru_cache
import time
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


def ollama_invoke(
    prompts: list[str], 
    model: str ="qwen2.5:14b",
    temperature: float =0.0
):
    llm = get_llm()
    reponse = llm.invoke(prompts)
    return reponse
    

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


def embed_documents(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """
    手动分批编码文档
    
    Args:
        texts: 要编码的文本列表
        batch_size: 每批处理的文本数量（根据显存/内存调整）
    
    Returns:
        嵌入向量列表，形状为 (len(texts), embedding_dim)
    """
    
    if not texts:
        return []

    embeder = get_ollama_embedding()
    all_embeddings = []
    total = len(texts)
    
    for i in range(0, total, batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            # 发送单批次请求
            response = embeder(batch)
            all_embeddings.extend(response['embeddings'])
            
            # 可选：添加小延迟避免 Ollama 过载
            if i + batch_size < total:
                time.sleep(0.01)  # 10ms
                
        except Exception as e:
            logger.error(f"Batch {i//batch_size + 1}/{ (total-1)//batch_size + 1} failed: {e}")
            
            # 降级策略：如果批次失败，尝试单个编码
            logger.warning(f"Falling back to single encoding for this batch")
            for text in batch:
                try:
                    resp = embeder(text)
                    all_embeddings.append(resp['embeddings'][0])
                except Exception as e2:
                    logger.error(f"Single text failed: {e2}")
                    # 使用零向量占位（假设 bge-m3 维度是 1024）
                    all_embeddings.append([0.0] * get_embedding_dim())
    
    return all_embeddings
    


if __name__ == "__main__":
    # print(get_embedding_dim()) 
    print(len(get_ollama_embedding()(["Hello world", "This is a test"])[0])) 