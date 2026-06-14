from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.reward import RewardCreate, RewardRead, RewardUpdate
from app.services import reward_service, season_service

router = APIRouter(tags=["rewards"])


async def _get_reward_or_404(db: DbSession, reward_id: int):
    reward = await reward_service.get_reward(db, reward_id)
    if reward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="리워드를 찾을 수 없습니다."
        )
    return reward


async def _require_season(db: DbSession, season_id: int) -> None:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )


@router.get("/seasons/{season_id}/rewards", response_model=list[RewardRead])
async def list_rewards(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[RewardRead]:
    """시즌별 리워드 도감 (로그인 유저 누구나)."""
    return await reward_service.list_rewards(db, season_id)


@router.post(
    "/seasons/{season_id}/rewards",
    response_model=RewardRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reward(
    season_id: int, payload: RewardCreate, db: DbSession, admin: AdminUser
) -> RewardRead:
    await _require_season(db, season_id)
    return await reward_service.create_reward(db, season_id, payload)


@router.patch("/rewards/{reward_id}", response_model=RewardRead)
async def update_reward(
    reward_id: int, payload: RewardUpdate, db: DbSession, admin: AdminUser
) -> RewardRead:
    reward = await _get_reward_or_404(db, reward_id)
    return await reward_service.update_reward(db, reward, payload, admin.id)


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward(reward_id: int, db: DbSession, admin: AdminUser) -> None:
    reward = await _get_reward_or_404(db, reward_id)
    await reward_service.delete_reward(db, reward)
