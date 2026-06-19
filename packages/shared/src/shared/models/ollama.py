"""shared/models/ollama.py — LLM + Embedding 单例，所有服务共用"""
from functools import lru_cache
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_groq import ChatGroq
from shared.configs.settings import OLLAMA_URL, LLM_MODEL, LLM_SQL, EMBED_MODEL, GROQ_API_KEY


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    print("preparing llm...")
    llm = ChatOllama(model=LLM_MODEL, 
                     temperature=0,
                    #   num_ctx=8192, 
                    #   num_gpu=999, 
                      base_url=OLLAMA_URL)
    print("✅ llm ready")
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
    print("preparing embeddings...")
    emb = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
    print("✅ embeddings ready")
    return emb

def get_embedding_dim(model=get_embedding()):
    vec = model.embed_query("test")
    return len(vec)

