

from functools import lru_cache

from langchain_ollama import ChatOllama, OllamaEmbeddings

from configs.settings import EMBED_MODEL, LLM_MODEL, OLLAMA_URL


@lru_cache(maxsize=1)
def get_embedding():
    print("preparing embeddings...")
    emd = OllamaEmbeddings(
        model=EMBED_MODEL,
        base_url=OLLAMA_URL,
    )
    print("✅ embeddings ready")
    return emd


@lru_cache(maxsize=1)
def get_llm():
    print("preparing llm...")
    # 共用的 LLM 实例（Agent 内部推理）
    llm = ChatOllama(
        model=LLM_MODEL,
        temperature=0.2,
        num_ctx=8192,
        num_gpu=999,
        base_url=OLLAMA_URL,
    )
    print("✅ llm ready")
    return llm
