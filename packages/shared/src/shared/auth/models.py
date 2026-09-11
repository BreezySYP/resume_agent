"""鉴权 ORM 模型（表结构由 db/migrations 管理，这里只声明映射）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider_account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )


class PersonalAccessToken(Base):
    """用户自助生成的 API key；只存 hash，明文只在创建时返回一次。"""

    __tablename__ = "personal_access_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    token_prefix: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )
