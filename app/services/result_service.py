"""게임 결과(최종 승자) 비즈니스 로직."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_session import GameResult
from app.schemas.result import ResultCreate


async def create_result(
    db: AsyncSession, session_id: int, data: ResultCreate
) -> GameResult:
    result = GameResult(
        session_id=session_id,
        subject_type=data.subject_type,
        subject_id=data.subject_id,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


async def list_results(db: AsyncSession, session_id: int) -> list[GameResult]:
    rows = await db.execute(
        select(GameResult)
        .where(GameResult.session_id == session_id)
        .order_by(GameResult.id)
    )
    return list(rows.scalars().all())
