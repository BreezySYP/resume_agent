"""共享 SQLAlchemy ORM 基类（各服务模型统一挂在一个 metadata 下）。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
