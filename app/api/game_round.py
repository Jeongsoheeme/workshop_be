from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.game_round import GameRound
from app.schemas.game_round import (
    RoundCreate,
    RoundRead,
    RoundReveal,
    RoundUpdate,
)
from app.services import game_round_service, game_session_service
from app.services.game_round_service import RoundConflict
from app.websocket.events import broadcast_round_revealed, broadcast_round_started

router = APIRouter(tags=["game-rounds"])


async def _get_session_or_404(db: DbSession, session_id: int):
    session = await game_session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )
    return session


async def _get_round_or_404(db: DbSession, round_id: int) -> GameRound:
    round_ = await game_round_service.get_round(db, round_id)
    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="라운드를 찾을 수 없습니다."
        )
    return round_


async def _reveal_for(db: DbSession, round_: GameRound) -> RoundReveal:
    total, dist = await game_round_service.round_distribution(db, round_.id)
    return RoundReveal(
        round_id=round_.id,
        correct_answer=round_.correct_answer,
        total_submissions=total,
        distribution=dist,
    )


@router.post(
    "/sessions/{session_id}/rounds",
    response_model=RoundRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_round(
    session_id: int, payload: RoundCreate, db: DbSession, admin: AdminUser
) -> GameRound:
    await _get_session_or_404(db, session_id)
    return await game_round_service.create_round(db, session_id, payload, admin.id)


@router.get("/sessions/{session_id}/rounds", response_model=list[RoundRead])
async def list_rounds(
    session_id: int, db: DbSession, user: CurrentUser
) -> list[GameRound]:
    return await game_round_service.list_rounds(db, session_id)


@router.get("/sessions/{session_id}/rounds/current", response_model=RoundRead)
async def current_round(
    session_id: int, db: DbSession, user: CurrentUser
) -> GameRound:
    """재접속 시 현재 진행 중인 라운드 복구용."""
    round_ = await game_round_service.get_open_round(db, session_id)
    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진행 중인 라운드가 없습니다.",
        )
    return round_


@router.get("/rounds/{round_id}", response_model=RoundRead)
async def get_round(round_id: int, db: DbSession, user: CurrentUser) -> GameRound:
    return await _get_round_or_404(db, round_id)


@router.patch("/rounds/{round_id}", response_model=RoundRead)
async def update_round(
    round_id: int, payload: RoundUpdate, db: DbSession, admin: AdminUser
) -> GameRound:
    round_ = await _get_round_or_404(db, round_id)
    return await game_round_service.update_round(db, round_, payload, admin.id)


@router.post("/rounds/{round_id}/open", response_model=RoundRead)
async def open_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> GameRound:
    round_ = await _get_round_or_404(db, round_id)
    try:
        round_ = await game_round_service.open_round(db, round_, admin.id)
    except RoundConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    await broadcast_round_started(round_)
    return round_


@router.post("/rounds/{round_id}/close", response_model=RoundReveal)
async def close_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundReveal:
    round_ = await _get_round_or_404(db, round_id)
    try:
        round_ = await game_round_service.close_round(db, round_, admin.id)
    except RoundConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    reveal = await _reveal_for(db, round_)
    await broadcast_round_revealed(round_, reveal.total_submissions, reveal.distribution)
    return reveal


@router.get("/rounds/{round_id}/reveal", response_model=RoundReveal)
async def reveal_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundReveal:
    round_ = await _get_round_or_404(db, round_id)
    return await _reveal_for(db, round_)
