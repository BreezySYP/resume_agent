"""auth_service 私有配置：只包含「签发侧 / 登录侧」的东西。

私钥、GitHub OAuth 凭证、前端白名单、client credentials、登录 code TTL
都只被本服务使用，因此**不放进 shared 的 Settings**——shared 是全仓库共享代码，
出现在那里的配置项等于所有服务都能读到（私钥尤其不能）。
验签公钥属于验证侧，仍在 `shared.configs.settings`。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AuthServiceSettings(BaseSettings):
    """仅 auth_service 读取的环境变量。

    优先级：真实环境变量（compose 注入 .env.auth） > 仓库根 `.env` > 默认值。
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # RS256 私钥（base64 编码的 PEM）。生成：
    #   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 | base64 -w0
    auth_jwt_private_key_b64: str = Field(default="", validation_alias="AUTH_JWT_PRIVATE_KEY_B64")
    # 登录 code 有效期（秒）
    auth_login_code_ttl: int = Field(default=60, validation_alias="AUTH_LOGIN_CODE_TTL")

    # ── GitHub OAuth ──────────────────────────────────────────────────
    github_oauth_client_id: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_ID")
    github_oauth_client_secret: str = Field(default="", validation_alias="GITHUB_OAUTH_CLIENT_SECRET")
    auth_redirect_uri: str = Field(
        default="http://localhost:8016/api/auth/callback/github",
        validation_alias="AUTH_REDIRECT_URI",
    )
    auth_admin_github_logins: str = Field(default="", validation_alias="AUTH_ADMIN_GITHUB_LOGINS")

    # ── token / 前端 / 服务凭证 ───────────────────────────────────────
    auth_session_days: int = Field(default=7, validation_alias="AUTH_SESSION_DAYS")
    auth_frontend_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias="AUTH_FRONTEND_ORIGINS",
    )
    auth_client_credentials: list[dict[str, Any]] = Field(
        default=[],
        validation_alias="AUTH_CLIENT_CREDENTIALS",
    )


@lru_cache
def get_auth_service_settings() -> AuthServiceSettings:
    return AuthServiceSettings()
