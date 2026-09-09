"""对话线程归属（thread -> user）ORM 访问。

Redis checkpoint 本身不记录所有者；表结构由 db/migrations 管理。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.db.base import Base
from shared.db.mysql import SessionLocal
from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column


class ConversationThread(Base):
    __tablename__ = "conversations"

    thread_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )


def get_thread_owner(thread_id: str) -> dict[str, Any] | None:
    with SessionLocal() as session:
        row = session.get(ConversationThread, thread_id)
    if row is None:
        return None
    return {"thread_id": row.thread_id, "user_id": row.user_id}


def claim_thread(thread_id: str, user_id: str) -> None:
    """声明线程归属：已属于别人时抛 PermissionError。"""
    with SessionLocal() as session:
        row = session.get(ConversationThread, thread_id)
        if row is not None and row.user_id != user_id:
            raise PermissionError(f"thread {thread_id} 已属于其他用户")
        if row is None:
            session.add(ConversationThread(thread_id=thread_id, user_id=user_id))
            session.commit()
