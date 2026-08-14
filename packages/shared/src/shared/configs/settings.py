"""shared/configs/settings.py — 全局配置（pydantic-settings，所有服务共用）"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理所有服务的环境变量配置。

    真实环境变量的优先级高于 `.env` 文件；`.env` 不存在时静默忽略。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ────────────────────────────────────────────────────────────
    ollama_url: str = "http://localhost:11434"
    deep_seek_key: str = ""
    llm_model: str = "qwen2.5:14b"
    llm_sql: str = "qwen2.5-coder:14b"
    embed_model: str = "nomic-embed-text"
    groq_api_key: str = ""

    # ── 存储 ───────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    vs_index_name: str = "multi_agent_rag"

    mysql_root_user: str = "root"
    mysql_password: str = Field(default="changeit", validation_alias="MYSQL_ROOT_PASSWORD")
    mysql_host: str = Field(default="host.docker.internal", validation_alias="MYSQL_URL")
    mysql_port: int = 3306
    mysql_db: str = Field(default="mydb", validation_alias="MYSQL_DATABASE")

    minio_url: str = "http://localhost:9000"
    minio_user: str = Field(default="admin", validation_alias="MINIO_ROOT_USER")
    minio_password: str = Field(default="changeit", validation_alias="MINIO_ROOT_PASSWORD")
    minio_bucket: str = "skills"

    qdrant_url: str = "http://host.docker.internal:6333"
    cuda_rerank_url: str = "http://host.docker.internal:8000/api/v1/rerank"

    # ── 可观测性 ───────────────────────────────────────────────────────
    tempo_url: str = ""
    loki_push_url: str = ""
    env: str = ""
    app_name: str = Field(default="", validation_alias="NAME")

    # ── 应用 ───────────────────────────────────────────────────────────
    thread_id: str = "agent_001"
    langsmith_project: str = Field(default="monorepo_agent", validation_alias="LANGCHAIN_PROJECT")

    # ── Web ────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    @property
    def graph_config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}


@lru_cache
def get_settings() -> Settings:
    return Settings()


_settings = get_settings()

# 兼容旧的模块级常量引用（所有服务都直接 import 这些名字）
OLLAMA_URL = _settings.ollama_url
DEEP_SEEK_KEY = _settings.deep_seek_key
LLM_MODEL = _settings.llm_model
LLM_SQL = _settings.llm_sql
EMBED_MODEL = _settings.embed_model
GROQ_API_KEY = _settings.groq_api_key

REDIS_URL = _settings.redis_url
VS_INDEX_NAME = _settings.vs_index_name

MYSQL_ROOT_USER = _settings.mysql_root_user
MYSQL_PASSWORD = _settings.mysql_password
MYSQL_HOST = _settings.mysql_host
MYSQL_PORT = _settings.mysql_port
MYSQL_DB = _settings.mysql_db

MINIO_URL = _settings.minio_url
MINIO_USER = _settings.minio_user
MINIO_PASSWORD = _settings.minio_password
MINIO_BUCKET = _settings.minio_bucket

QDRANT_URL = _settings.qdrant_url
CUDA_RERANK_URL = _settings.cuda_rerank_url

TEMPO_URL = _settings.tempo_url
LOKI_PUSH_URL = _settings.loki_push_url
ENV = _settings.env
APP_NAME = _settings.app_name

THREAD_ID = _settings.thread_id
GRAPH_CONFIG = _settings.graph_config
LANGSMITH_PROJECT = _settings.langsmith_project

CORS_ORIGINS = _settings.cors_origins

__all__ = [
    "OLLAMA_URL",
    "DEEP_SEEK_KEY",
    "LLM_MODEL",
    "LLM_SQL",
    "EMBED_MODEL",
    "GROQ_API_KEY",
    "REDIS_URL",
    "VS_INDEX_NAME",
    "MYSQL_ROOT_USER",
    "MYSQL_PASSWORD",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DB",
    "MINIO_URL",
    "MINIO_USER",
    "MINIO_PASSWORD",
    "MINIO_BUCKET",
    "QDRANT_URL",
    "CUDA_RERANK_URL",
    "TEMPO_URL",
    "LOKI_PUSH_URL",
    "ENV",
    "APP_NAME",
    "THREAD_ID",
    "GRAPH_CONFIG",
    "LANGSMITH_PROJECT",
    "CORS_ORIGINS",
]
