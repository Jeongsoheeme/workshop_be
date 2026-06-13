"""WebSocket 엔드포인트.

연결 시 토큰을 query parameter로 받아 인증.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = int(payload["sub"])
    team_id = payload.get("team_id")

    await manager.connect(websocket, user_id, team_id)
    try:
        while True:
            data = await websocket.receive_json()
            # 클라이언트 → 서버 메시지 처리 (채팅, 버튼 등)
            # 추후 메시지 타입별 핸들러 등록
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            # TODO: chat, button_press 등 처리
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, team_id)
