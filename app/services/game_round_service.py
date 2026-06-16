"""게임 세션 내부 라운드(진행도) 비즈니스 로직.

세션당 동시에 1개의 라운드만 'open' 상태일 수 있다.
"""

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_round import GameRound, RoundSubmission
from app.models.game_session import GameChatLog, GameSession
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.timetable import Timetable
from app.models.user import User
from app.schemas.game_round import RoundCreate, RoundUpdate


class RoundConflict(Exception):
    """라운드 상태/제출 충돌 (이미 마감, 중복 제출 등)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _judge(correct: str | None, answer: str) -> bool:
    """정답 판정. 앞뒤 공백 무시 + 대소문자 무시."""
    if correct is None:
        return False
    return correct.strip().casefold() == answer.strip().casefold()


# --- 조회/생성 ---------------------------------------------------------------


async def create_round(
    db: AsyncSession, session_id: int, data: RoundCreate, admin_id: int
) -> GameRound:
    round_ = GameRound(
        session_id=session_id,
        order_index=data.order_index,
        prompt=data.prompt,
        media_url=data.media_url,
        options=data.options,
        correct_answer=data.correct_answer,
        created_by=admin_id,
    )
    db.add(round_)
    await db.commit()
    await db.refresh(round_)
    return round_


async def list_rounds(db: AsyncSession, session_id: int) -> list[GameRound]:
    result = await db.execute(
        select(GameRound)
        .where(GameRound.session_id == session_id)
        .order_by(GameRound.order_index)
    )
    return list(result.scalars().all())


async def get_round(db: AsyncSession, round_id: int) -> GameRound | None:
    result = await db.execute(select(GameRound).where(GameRound.id == round_id))
    return result.scalar_one_or_none()


async def get_open_round(db: AsyncSession, session_id: int) -> GameRound | None:
    """세션에서 현재 진행 중(open)인 라운드. 없으면 None."""
    result = await db.execute(
        select(GameRound).where(
            GameRound.session_id == session_id, GameRound.status == "open"
        )
    )
    return result.scalar_one_or_none()


async def list_chat_logs(
    db: AsyncSession, session_id: int, round_id: int | None = None
) -> list[dict]:
    """운영자용 채팅 로그. 서버 저장 순서로 빠른 답변 순위를 판단한다."""
    stmt = (
        select(
            GameChatLog.id,
            GameChatLog.session_id,
            GameChatLog.round_id,
            GameChatLog.user_id,
            User.nickname,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
            GameChatLog.message,
            GameChatLog.is_correct,
            GameChatLog.server_time,
        )
        .join(User, User.id == GameChatLog.user_id)
        .join(GameSession, GameSession.id == GameChatLog.session_id)
        .join(Timetable, Timetable.id == GameSession.timetable_id)
        .outerjoin(
            TeamMembership,
            and_(
                TeamMembership.season_id == Timetable.season_id,
                TeamMembership.user_id == GameChatLog.user_id,
            ),
        )
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .where(GameChatLog.session_id == session_id)
        .order_by(GameChatLog.server_time, GameChatLog.id)
    )
    if round_id is not None:
        stmt = stmt.where(GameChatLog.round_id == round_id)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def update_round(
    db: AsyncSession, round_: GameRound, data: RoundUpdate, admin_id: int
) -> GameRound:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(round_, key, value)
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


# --- 상태 전이 ---------------------------------------------------------------


async def open_round(
    db: AsyncSession, round_: GameRound, admin_id: int
) -> GameRound:
    if round_.status == "closed":
        raise RoundConflict("이미 마감된 라운드는 다시 열 수 없습니다.")
    other = await get_open_round(db, round_.session_id)
    if other is not None and other.id != round_.id:
        raise RoundConflict(
            f"이미 열린 라운드(order={other.order_index})가 있습니다. 먼저 마감하세요."
        )
    round_.status = "open"
    round_.opened_at = _utcnow()
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


async def close_round(
    db: AsyncSession, round_: GameRound, admin_id: int
) -> GameRound:
    if round_.status != "open":
        raise RoundConflict("열려 있는(open) 라운드만 마감할 수 있습니다.")
    round_.status = "closed"
    round_.closed_at = _utcnow()
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


# --- 제출 -------------------------------------------------------------------


async def submit_answer(
    db: AsyncSession, round_: GameRound, user_id: int, answer: str
) -> RoundSubmission:
    """button/vote 타입 1인 1답 제출. 중복 제출/마감 시 RoundConflict."""
    if round_.status != "open":
        raise RoundConflict("진행 중인 라운드가 아닙니다.")

    submission = RoundSubmission(
        round_id=round_.id,
        user_id=user_id,
        answer=answer,
        is_correct=_judge(round_.correct_answer, answer),
        server_time=_utcnow(),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RoundConflict("이미 이 라운드에 제출했습니다.") from exc
    await db.refresh(submission)
    return submission


async def record_chat(
    db: AsyncSession,
    session_id: int,
    round_: GameRound | None,
    user_id: int,
    message: str,
) -> GameChatLog:
    """chat 타입 채팅 1건 기록. round_ 가 있으면 정답 판정까지 한다."""
    log = GameChatLog(
        session_id=session_id,
        round_id=round_.id if round_ else None,
        user_id=user_id,
        message=message,
        is_correct=_judge(round_.correct_answer, message) if round_ else False,
        server_time=_utcnow(),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def round_distribution(
    db: AsyncSession, round_id: int
) -> tuple[int, dict[str, int]]:
    """라운드 제출 분포 (answer -> 개수)와 총 제출 수."""
    result = await db.execute(
        select(RoundSubmission.answer, func.count())
        .where(RoundSubmission.round_id == round_id)
        .group_by(RoundSubmission.answer)
    )
    dist = {answer: int(count) for answer, count in result.all()}
    return sum(dist.values()), dist
