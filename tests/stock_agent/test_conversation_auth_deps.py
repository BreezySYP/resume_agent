"""conversation owner-or-admin 路由依赖单测（mock 归属查询，不触数据库）。"""

from __future__ import annotations

import pytest
from service import conversation_auth
from shared.auth.errors import NotFoundError, PermissionDeniedError

NORMAL_USER = {
    "id": "u1",
    "email": "u1@example.com",
    "name": "u1",
    "avatar_url": None,
    "is_admin": False,
}
OTHER_USER = {**NORMAL_USER, "id": "u2"}
ADMIN_USER = {**NORMAL_USER, "id": "admin", "is_admin": True}


def _patch_owner(monkeypatch, owner):
    monkeypatch.setattr(conversation_auth, "get_thread_owner", lambda thread_id: owner)


def test_owner_can_read_thread(monkeypatch) -> None:
    _patch_owner(monkeypatch, {"thread_id": "t1", "user_id": "u1"})
    conversation_auth.require_conversation_owner_or_admin("t1", NORMAL_USER)


def test_admin_can_read_others_thread(monkeypatch) -> None:
    _patch_owner(monkeypatch, {"thread_id": "t1", "user_id": "u2"})
    conversation_auth.require_conversation_owner_or_admin("t1", ADMIN_USER)


def test_other_user_gets_not_found(monkeypatch) -> None:
    _patch_owner(monkeypatch, {"thread_id": "t1", "user_id": "u2"})
    with pytest.raises(NotFoundError):
        conversation_auth.require_conversation_owner_or_admin("t1", NORMAL_USER)


def test_missing_thread_gets_not_found(monkeypatch) -> None:
    _patch_owner(monkeypatch, None)
    with pytest.raises(NotFoundError):
        conversation_auth.require_conversation_owner_or_admin("t1", NORMAL_USER)


def test_claim_conflict_gets_403(monkeypatch) -> None:
    _patch_owner(monkeypatch, {"thread_id": "t1", "user_id": "u2"})
    with pytest.raises(PermissionDeniedError):
        conversation_auth.require_conversation_claim("t1", NORMAL_USER)


def test_claim_allowed_for_new_thread(monkeypatch) -> None:
    _patch_owner(monkeypatch, None)
    conversation_auth.require_conversation_claim("t-new", NORMAL_USER)


def test_claim_allowed_for_admin(monkeypatch) -> None:
    _patch_owner(monkeypatch, {"thread_id": "t1", "user_id": "u2"})
    conversation_auth.require_conversation_claim("t1", ADMIN_USER)
