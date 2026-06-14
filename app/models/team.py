from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    del_yn: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
        comment="소프트 삭제 여부",
    )

    # --- relationships ---
    season: Mapped["Season"] = relationship(back_populates="teams")
    memberships: Mapped[list["TeamMembership"]] = relationship(back_populates="team")
    team_buffs: Mapped[list["TeamBuff"]] = relationship(back_populates="team")
