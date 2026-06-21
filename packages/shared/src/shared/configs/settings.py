"""shared/configs/settings.py — 全局配置，所有服务共用"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
LLM_MODEL    = os.getenv("LLM_MODEL",    "qwen2.5:14b")
LLM_SQL      = os.getenv("LLM_SQL",      "qwen2.5-coder:14b")
EMBED_MODEL  = os.getenv("EMBED_MODEL",  "nomic-embed-text")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

REDIS_URL     = os.getenv("REDIS_URL",     "redis://localhost:6379")
VS_INDEX_NAME = os.getenv("VS_INDEX_NAME", "multi_agent_rag")

MYSQL_ROOT_USER     = os.getenv("MYSQL_ROOT_USER",         "root")
MYSQL_PASSWORD = os.getenv("MYSQL_ROOT_PASSWORD", "changeit")
MYSQL_HOST     = os.getenv("MYSQL_URL",           "host.docker.internal")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT",      "3306"))
MYSQL_DB       = os.getenv("MYSQL_DATABASE",      "mydb")

MINIO_URL      = os.getenv("MINIO_URL",           "http://localhost:9000")
MINIO_USER     = os.getenv("MINIO_ROOT_USER",     "admin")
MINIO_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "changeit")
MINIO_BUCKET   = os.getenv("MINIO_BUCKET",        "skills")

QDRANT_URL  = os.getenv("QDRANT_URL", "http://host.docker.internal:6333")
CUDA_RERANK_URL = os.getenv("CUDA_RERANK_URL", "http://host.docker.internal:8000/api/v1/rerank")

GRAFANA_URL = os.getenv("GRAFANA_URL", "")

THREAD_ID    = os.getenv("THREAD_ID", "agent_001")
GRAPH_CONFIG = {"configurable": {"thread_id": THREAD_ID}}

LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "monorepo_agent")
