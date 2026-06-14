from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamCreate(BaseModel):
    name: str


class TeamUpdate(BaseModel):
    name: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    name: str
    created_at: datetime


class TeamMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    role: str
    point: int
    profile_image: str | None


class MemberAssign(BaseModel):
    user_id: int


class SeasonMembership(BaseModel):
    """시즌 내 유저-팀 배정 현황 (운영자 화면용)."""

    user_id: int
    team_id: int


class MyTeam(BaseModel):
    """선택 시즌에서 내 소속 팀 (없으면 team_id=null)."""

    team_id: int | None
    name: str | None
