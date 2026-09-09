"""users / oauth_accounts 数据访问（SQLAlchemy ORM）。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select

from shared.auth.models import OAuthAccount, User
from shared.db.mysql import SessionLocal


def _user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "is_admin": bool(user.is_admin),
    }


def get_user(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
    return _user_dict(user) if user else None


def get_user_by_oauth(provider: str, provider_account_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        account = session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        if account is None:
            return None
        user = session.get(User, account.user_id)
    return _user_dict(user) if user else None


def upsert_oauth_user(
    *,
    provider: str,
    account_id: str,
    username: str | None = None,
    email: str | None = None,
    name: str | None = None,
    avatar_url: str | None = None,
    admin_logins: set[str] | None = None,
) -> dict[str, Any]:
    """GitHub 登录后 upsert 用户；命中 AUTH_ADMIN_GITHUB_LOGINS 则提升为管理员。"""
    admins = admin_logins or set()
    with SessionLocal() as session:
        account = session.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == account_id,
            )
        )
        if account is not None:
            user = session.get(User, account.user_id)
            if user is None:
                raise RuntimeError("oauth_accounts 引用了不存在的用户")
            if not user.is_admin and username in admins:
                user.is_admin = True
            if email:
                user.email = email
            if name:
                user.name = name
            if avatar_url:
                user.avatar_url = avatar_url
            account.provider_username = username or account.provider_username
            account.email = email or account.email
            account.name = name or account.name
            account.avatar_url = avatar_url or account.avatar_url
            session.commit()
            session.refresh(user)
            return _user_dict(user)

        user = User(
            id=uuid4().hex,
            email=email,
            name=name or "",
            avatar_url=avatar_url,
            is_admin=username in admins,
        )
        session.add(user)
        session.flush()
        session.add(
            OAuthAccount(
                provider=provider,
                provider_account_id=account_id,
                user_id=user.id,
                provider_username=username,
                email=email,
                name=name or "",
                avatar_url=avatar_url,
            )
        )
        session.commit()
        session.refresh(user)
        return _user_dict(user)
