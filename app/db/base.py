from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class CreatedAtMixin:
    """created_at 만 가지는 테이블용 mixin (로그성 테이블)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
        comment="생성 시각",
    )


class TimestampMixin(CreatedAtMixin):
    """created_at + updated_at 공통 timestamp mixin."""

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="최종 수정 시각",
    )
