"""WebSocket 클라이언트 → 서버 메시지 핸들러.

메시지 타입별 핸들러를 레지스트리에 등록하고 dispatch() 가 라우팅한다.
새 핸들러는 @register("타입") 데코레이터로 추가하면 된다.

핸들러 시그니처:
    async def handler(ctx: MessageContext, data: dict[str, Any]) -> None
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

if TYPE_CHECKING:
    from app.websocket.manager import ConnectionManager


class MessageContext:
    """핸들러가 응답을 보낼 때 필요한 컨텍스트."""

    def __init__(
        self,
        websocket: WebSocket,
        manager: "ConnectionManager",
        user_id: int,
        team_id: int | None,
    ) -> None:
        self.websocket = websocket
        self.manager = manager
        self.user_id = user_id
        self.team_id = team_id


Handler = Callable[[MessageContext, dict[str, Any]], Awaitable[None]]

_HANDLERS: dict[str, Handler] = {}


def register(msg_type: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _HANDLERS[msg_type] = fn
        return fn

    return decorator


async def dispatch(ctx: MessageContext, data: dict[str, Any]) -> None:
    """수신 메시지를 타입에 맞는 핸들러로 전달."""
    msg_type = data.get("type")
    handler = _HANDLERS.get(msg_type)
    if handler is None:
        await ctx.websocket.send_json(
            {"type": "error", "detail": f"알 수 없는 메시지 타입: {msg_type!r}"}
        )
        return
    await handler(ctx, data)


@register("ping")
async def _handle_ping(ctx: MessageContext, data: dict[str, Any]) -> None:
    await ctx.websocket.send_json({"type": "pong"})
