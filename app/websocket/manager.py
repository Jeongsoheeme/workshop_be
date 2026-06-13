"""WebSocket 연결 관리.

전체 broadcast, 팀별 broadcast, 개인 message 전송을 담당.
18명 규모라 메모리 기반 관리로 충분.
"""

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> list of WebSockets (한 유저가 여러 탭 가능성)
        self._user_connections: dict[int, list[WebSocket]] = defaultdict(list)
        # team_id -> set of user_ids
        self._team_members: dict[int, set[int]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: int, team_id: int | None) -> None:
        await websocket.accept()
        self._user_connections[user_id].append(websocket)
        if team_id is not None:
            self._team_members[team_id].add(user_id)

    def disconnect(self, websocket: WebSocket, user_id: int, team_id: int | None) -> None:
        if websocket in self._user_connections[user_id]:
            self._user_connections[user_id].remove(websocket)
        if not self._user_connections[user_id]:
            self._user_connections.pop(user_id, None)
            if team_id is not None:
                self._team_members[team_id].discard(user_id)

    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> None:
        for ws in self._user_connections.get(user_id, []):
            await ws.send_json(message)

    async def send_to_team(self, team_id: int, message: dict[str, Any]) -> None:
        for user_id in self._team_members.get(team_id, set()):
            await self.send_to_user(user_id, message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for user_id in list(self._user_connections.keys()):
            await self.send_to_user(user_id, message)


manager = ConnectionManager()
