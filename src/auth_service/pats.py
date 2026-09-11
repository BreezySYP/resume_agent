"""Personal access token 管理（仅 auth_service 使用）。

负责生成/列表/撤销；明文只在创建时返回一次，库里只存哈希。
验证路径在 `shared.auth.pats.verify_pat`（各 API 服务共用）。
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from shared.auth.models import PersonalAccessToken
from shared.auth.pats import PAT_PREFIX, hash_token
from shared.db.mysql import SessionLocal
from sqlalchemy import select

_TOKEN_BYTES = 32
_PREFIX_LEN = 12  # 存 "pat_" + 前 8 位，列表展示用


def _to_dict(row: PersonalAccessToken) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "token_prefix": row.token_prefix,
        "is_admin": bool(row.is_admin),
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "revoked_at": row.revoked_at,
        "last_used_at": row.last_used_at,
    }


def create_pat(
    *,
    user_id: str,
    name: str = "",
    is_admin: bool = False,
    expires_days: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """创建 PAT，返回 (明文 token, 记录信息)；明文仅此一次。"""
    raw = PAT_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)
    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_days)
        if expires_days is not None
        else None
    )
    row = PersonalAccessToken(
        id=uuid4().hex,
        user_id=user_id,
        name=name,
        token_prefix=raw[:_PREFIX_LEN],
        token_hash=hash_token(raw),
        is_admin=is_admin,
        expires_at=expires_at,
    )
    with SessionLocal() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return raw, _to_dict(row)


def list_pats(user_id: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.user_id == user_id)
            .order_by(PersonalAccessToken.created_at.desc())
        ).all()
        return [_to_dict(row) for row in rows]


def revoke_pat(user_id: str, token_id: str, *, allow_admin: bool = False) -> bool:
    """撤销自己的 token；allow_admin 为 True 时可撤销任意 token。返回是否存在。"""
    with SessionLocal() as session:
        row = session.get(PersonalAccessToken, token_id)
        if row is None:
            return False
        if row.user_id != user_id and not allow_admin:
            return False
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            session.commit()
        return True
