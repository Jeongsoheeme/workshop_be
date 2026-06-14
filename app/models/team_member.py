from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin


class TeamMembership(Base, CreatedAtMixin):
    """시즌별 유저-팀 소속 (한 유저는 시즌마다 다른 팀에 속할 수 있다)."""

    __tablename__ = "team_members"
    __table_args__ = (
        # 한 시즌에서 유저는 최대 한 팀
        UniqueConstraint("season_id", "user_id", name="uq_team_members_season_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_team_members_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", name="fk_team_members_team"),
        nullable=False,
        comment="소속 팀 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_team_members_user"),
        nullable=False,
        comment="유저 ID",
    )

    # --- relationships ---
    season: Mapped["Season"] = relationship()
    team: Mapped["Team"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")
