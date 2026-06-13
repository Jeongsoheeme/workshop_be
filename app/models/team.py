from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class Team(Base, CreatedAtMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_teams_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="팀 이름")
