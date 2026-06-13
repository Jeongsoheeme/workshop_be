from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.game_session import GameSession
from app.schemas.roulette import (
    CommitmentResponse,
    RouletteSpinRequest,
    RouletteSpinResult,
    SeedRevealResponse,
)
from app.services import game_session_service, roulette_service
from app.websocket.events import broadcast_roulette_result

router = APIRouter(tags=["roulette"])


async def _get_session_or_404(db: DbSession, session_id: int) -> GameSession:
    session = await game_session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )
    return session


def _require_seed(session: GameSession) -> str:
    if session.seed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="세션 시드가 아직 없습니다. 게임 시작(in_progress) 후 가능합니다.",
        )
    return session.seed


@router.get(
    "/sessions/{session_id}/roulette/commitment", response_model=CommitmentResponse
)
async def get_commitment(
    session_id: int, db: DbSession, user: CurrentUser
) -> CommitmentResponse:
    session = await _get_session_or_404(db, session_id)
    seed = _require_seed(session)
    return CommitmentResponse(
        session_id=session_id, commitment=roulette_service.commitment(seed)
    )


@router.post(
    "/sessions/{session_id}/roulette/spin", response_model=RouletteSpinResult
)
async def spin(
    session_id: int, payload: RouletteSpinRequest, db: DbSession, admin: AdminUser
) -> RouletteSpinResult:
    session = await _get_session_or_404(db, session_id)
    seed = _require_seed(session)

    index = roulette_service.draw_index(seed, payload.nonce, len(payload.options))
    selected = payload.options[index]

    await broadcast_roulette_result(session_id, payload.nonce, index, selected)

    return RouletteSpinResult(
        session_id=session_id,
        nonce=payload.nonce,
        options=payload.options,
        selected_index=index,
        selected=selected,
        commitment=roulette_service.commitment(seed),
    )


@router.get("/sessions/{session_id}/roulette/seed", response_model=SeedRevealResponse)
async def reveal_seed(
    session_id: int, db: DbSession, admin: AdminUser
) -> SeedRevealResponse:
    session = await _get_session_or_404(db, session_id)
    seed = _require_seed(session)
    # 공정성 검증을 위한 시드 공개는 게임 종료 후에만 허용
    if session.state != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="시드 공개는 게임 종료(done) 후에만 가능합니다.",
        )
    return SeedRevealResponse(
        session_id=session_id,
        seed=seed,
        commitment=roulette_service.commitment(seed),
    )
