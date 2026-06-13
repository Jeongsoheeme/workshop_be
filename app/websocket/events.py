"""서버 → 클라이언트 이벤트 브로드캐스트.

REST API 등에서 발생한 상태 변화를 WebSocket 접속자에게 알린다.
manager 싱글턴을 통해 같은 프로세스의 모든 연결로 전송된다.
"""

from app.models.game_session import GameResult, GameScoreLog, GameSession
from app.websocket.manager import manager


async def broadcast_session_state(session: GameSession) -> None:
    """게임 세션 상태 변경을 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "session_state_changed",
            "session_id": session.id,
            "timetable_id": session.timetable_id,
            "state": session.state,
        }
    )


async def broadcast_score_recorded(score: GameScoreLog) -> None:
    """점수 기록을 전체 접속자에게 브로드캐스트 (라이브 스코어보드)."""
    await manager.broadcast(
        {
            "type": "score_recorded",
            "session_id": score.session_id,
            "subject_type": score.subject_type,
            "subject_id": score.subject_id,
            "score": score.score,
        }
    )


async def broadcast_result_recorded(result: GameResult) -> None:
    """최종 결과 기록을 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "result_recorded",
            "session_id": result.session_id,
            "subject_type": result.subject_type,
            "subject_id": result.subject_id,
        }
    )


async def broadcast_roulette_result(
    session_id: int, nonce: int, selected_index: int, selected: str
) -> None:
    """룰렛/추첨 결과를 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "roulette_result",
            "session_id": session_id,
            "nonce": nonce,
            "selected_index": selected_index,
            "selected": selected,
        }
    )
