"""
config/settings.py
全局配置：从 .env 读取环境变量，暴露统一常量。
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# ── LLM ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen2.5:14b")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "nomic-embed-text")

# ── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
VS_INDEX_NAME   = os.getenv("VS_INDEX_NAME", "multi_agent_rag")

# ── Observability ────────────────────────────────────────────────────────────
GRAFANA_URL  = os.getenv("GRAFANA_URL", "")

# ── LangGraph ────────────────────────────────────────────────────────────────
THREAD_ID    = os.getenv("THREAD_ID", "dev_agent_rag_001")
GRAPH_CONFIG = {"configurable": {"thread_id": THREAD_ID}}
