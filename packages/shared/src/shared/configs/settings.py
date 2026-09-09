"""shared/configs/settings.py — 全局配置（pydantic-settings，所有服务共用）"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 把仓库根目录 `.env` 注入 os.environ（Tavily / LangSmith / OTel 等仍通过 os.getenv 读取），
# find_dotenv 从本文件所在目录向上查找，与进程启动目录无关。
# 优先级：真实环境变量（容器 -e / compose environment） > `.env` > 代码默认值。
load_dotenv(override=False)

_PROJECT_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    """集中管理所有服务的环境变量配置。

    优先级：真实环境变量（容器 -e / compose environment） > `.env` 文件 > 代码默认值。
    默认值只是兜底，容器化部署时请通过环境变量或 .env 覆盖；`.env` 不存在时静默忽略。
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
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

    # ── Auth（GitHub OAuth + JWT Bearer token）────────────────────────
    github_oauth_client_id: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_SECRET")
    auth_redirect_uri: str = Field(
        default="http://localhost:8004/api/auth/callback/github",
        validation_alias="AUTH_REDIRECT_URI",
    )
    auth_session_secret: str = Field(default="", validation_alias="AUTH_SESSION_SECRET")
    auth_session_days: int = Field(default=7, validation_alias="AUTH_SESSION_DAYS")
    auth_admin_github_logins: str = Field(default="", validation_alias="AUTH_ADMIN_GITHUB_LOGINS")
    auth_frontend_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias="AUTH_FRONTEND_ORIGINS",
    )

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
