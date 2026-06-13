"""서버 → 클라이언트 이벤트 브로드캐스트.

REST API 등에서 발생한 상태 변화를 WebSocket 접속자에게 알린다.
manager 싱글턴을 통해 같은 프로세스의 모든 연결로 전송된다.
"""

from app.models.game_session import GameSession
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
