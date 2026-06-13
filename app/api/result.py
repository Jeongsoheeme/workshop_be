from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.result import ResultCreate, ResultRead
from app.services import game_session_service, result_service, score_service
from app.websocket.events import broadcast_result_recorded

router = APIRouter(tags=["results"])


@router.post(
    "/sessions/{session_id}/results",
    response_model=ResultRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_result(
    session_id: int, payload: ResultCreate, db: DbSession, admin: AdminUser
) -> ResultRead:
    if await game_session_service.get_session(db, session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )
    if not await score_service.subject_exists(db, payload.subject_type, payload.subject_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="존재하지 않는 대상(team/user)입니다.",
        )
    result = await result_service.create_result(db, session_id, payload)
    await broadcast_result_recorded(result)
    return result


@router.get("/sessions/{session_id}/results", response_model=list[ResultRead])
async def list_results(
    session_id: int, db: DbSession, user: CurrentUser
) -> list[ResultRead]:
    return await result_service.list_results(db, session_id)
