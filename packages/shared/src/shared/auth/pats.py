"""Personal access token 验证（各 API 服务共用）。

PAT 的**生成/列表/撤销**在 auth_service（`src/auth_service/pats.py`）；
shared 只保留验证路径需要的部分：

- `PAT_PREFIX`：识别 `Authorization: Bearer pat_...`；
- `hash_token`：明文 → sha256（只存哈希，不存明文）；
- `verify_pat`：查库校验撤销/过期，返回归属用户与固化的权限。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from shared.auth.models import PersonalAccessToken
from shared.db.mysql import SessionLocal

PAT_PREFIX = "pat_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_pat(token: str) -> dict[str, Any] | None:
    """验证 PAT 是否有效；有效返回 {user_id, is_admin}，否则 None。"""
    token_hash = hash_token(token)
    now = datetime.now(UTC)
    with SessionLocal() as session:
        row = session.scalar(
            select(PersonalAccessToken).where(PersonalAccessToken.token_hash == token_hash)
        )
        if row is None or row.revoked_at is not None:
            return None
        if row.expires_at is not None and row.expires_at <= now:
            return None
        row.last_used_at = now
        result = {"user_id": row.user_id, "is_admin": bool(row.is_admin)}
        session.commit()
        return result
