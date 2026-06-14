"""팀 비즈니스 로직 (시즌별 팀 + 멤버십)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate


async def create_team(db: AsyncSession, season_id: int, data: TeamCreate) -> Team:
    team = Team(season_id=season_id, name=data.name)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def list_teams(db: AsyncSession, season_id: int) -> list[Team]:
    """삭제되지 않은 팀만."""
    result = await db.execute(
        select(Team)
        .where(Team.season_id == season_id, Team.del_yn.is_(False))
        .order_by(Team.id)
    )
    return list(result.scalars().all())


async def get_team(db: AsyncSession, team_id: int) -> Team | None:
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.del_yn.is_(False))
    )
    return result.scalar_one_or_none()


async def update_team(db: AsyncSession, team: Team, data: TeamUpdate) -> Team:
    team.name = data.name
    await db.commit()
    await db.refresh(team)
    return team


async def delete_team(db: AsyncSession, team: Team) -> None:
    """소프트 삭제. 해당 팀의 멤버십은 정리(하드 삭제)해 재배정을 풀어준다."""
    await db.execute(
        delete(TeamMembership).where(TeamMembership.team_id == team.id)
    )
    team.del_yn = True
    await db.commit()


# ---------- 멤버십 ----------

async def list_members(db: AsyncSession, team_id: int) -> list[User]:
    """팀 소속 유저 목록 (포인트 내림차순) — 멤버십 조인."""
    result = await db.execute(
        select(User)
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == team_id)
        .order_by(User.point.desc(), User.id)
    )
    return list(result.scalars().all())


async def list_season_memberships(
    db: AsyncSession, season_id: int
) -> list[TeamMembership]:
    result = await db.execute(
        select(TeamMembership).where(TeamMembership.season_id == season_id)
    )
    return list(result.scalars().all())


async def assign_member(
    db: AsyncSession, season_id: int, team_id: int, user_id: int
) -> TeamMembership:
    """유저를 시즌의 팀에 배정한다. 같은 시즌의 기존 배정은 교체한다."""
    await db.execute(
        delete(TeamMembership).where(
            TeamMembership.season_id == season_id,
            TeamMembership.user_id == user_id,
        )
    )
    membership = TeamMembership(season_id=season_id, team_id=team_id, user_id=user_id)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def unassign_member(db: AsyncSession, season_id: int, user_id: int) -> None:
    await db.execute(
        delete(TeamMembership).where(
            TeamMembership.season_id == season_id,
            TeamMembership.user_id == user_id,
        )
    )
    await db.commit()


async def get_my_team(
    db: AsyncSession, season_id: int, user_id: int
) -> Team | None:
    """선택 시즌에서 유저의 소속 팀 (없으면 None)."""
    result = await db.execute(
        select(Team)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .where(
            TeamMembership.season_id == season_id,
            TeamMembership.user_id == user_id,
            Team.del_yn.is_(False),
        )
    )
    return result.scalar_one_or_none()
