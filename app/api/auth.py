from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead
from app.services import season_service, team_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # 팀은 시즌별이므로, 활성 시즌에서의 소속 팀을 토큰/응답에 담는다.
    team_id: int | None = None
    active = await season_service.get_active_season(db)
    if active is not None:
        team = await team_service.get_my_team(db, active.id, user.id)
        team_id = team.id if team else None

    token = create_access_token(subject=user.id, role=user.role, team_id=team_id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        nickname=user.nickname,
        role=user.role,
        team_id=team_id,
    )


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUser) -> User:
    return user
