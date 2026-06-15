"""WebSocket 클라이언트 → 서버 메시지 핸들러.

메시지 타입별 핸들러를 레지스트리에 등록하고 dispatch() 가 라우팅한다.
새 핸들러는 @register("타입") 데코레이터로 추가하면 된다.

핸들러 시그니처:
    async def handler(ctx: MessageContext, data: dict[str, Any]) -> None
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import game_round_service
from app.services.game_round_service import RoundConflict
from app.websocket.events import (
    broadcast_chat_message,
    broadcast_submission_progress,
)

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


async def _error(ctx: MessageContext, detail: str) -> None:
    await ctx.websocket.send_json({"type": "error", "detail": detail})


@register("ping")
async def _handle_ping(ctx: MessageContext, data: dict[str, Any]) -> None:
    await ctx.websocket.send_json({"type": "pong"})


@register("join_session")
async def _handle_join_session(ctx: MessageContext, data: dict[str, Any]) -> None:
    """게임 상세 페이지 진입 — 해당 세션의 실시간 방에 합류."""
    session_id = data.get("session_id")
    if not isinstance(session_id, int):
        await _error(ctx, "session_id(정수)가 필요합니다.")
        return
    ctx.manager.join_session(session_id, ctx.user_id)
    await ctx.websocket.send_json({"type": "session_joined", "session_id": session_id})


@register("leave_session")
async def _handle_leave_session(ctx: MessageContext, data: dict[str, Any]) -> None:
    session_id = data.get("session_id")
    if isinstance(session_id, int):
        ctx.manager.leave_session(session_id, ctx.user_id)


@register("chat_message")
async def _handle_chat_message(ctx: MessageContext, data: dict[str, Any]) -> None:
    """chat 타입 게임의 채팅 입력. 현재 열린 라운드 기준으로 정답 판정 후 전파."""
    session_id = data.get("session_id")
    message = data.get("message")
    if not isinstance(session_id, int) or not isinstance(message, str):
        await _error(ctx, "session_id(정수)와 message(문자열)가 필요합니다.")
        return
    message = message.strip()
    if not message:
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_open_round(db, session_id)
        chat = await game_round_service.record_chat(
            db, session_id, round_, ctx.user_id, message
        )
        nickname = await db.scalar(
            select(User.nickname).where(User.id == ctx.user_id)
        )

    await broadcast_chat_message(chat, nickname or "익명")


@register("submit_answer")
async def _handle_submit_answer(ctx: MessageContext, data: dict[str, Any]) -> None:
    """button/vote 타입 게임의 보기 선택 제출. 1인 1답."""
    round_id = data.get("round_id")
    answer = data.get("answer")
    if not isinstance(round_id, int) or not isinstance(answer, str):
        await _error(ctx, "round_id(정수)와 answer(문자열)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, round_id)
        if round_ is None:
            await _error(ctx, "라운드를 찾을 수 없습니다.")
            return
        try:
            await game_round_service.submit_answer(
                db, round_, ctx.user_id, answer
            )
        except RoundConflict as exc:
            await _error(ctx, str(exc))
            return
        total, _dist = await game_round_service.round_distribution(db, round_id)

    # 제출자 본인에게는 접수 확인만 (정답 여부는 공정성상 마감 때 공개)
    await ctx.websocket.send_json(
        {"type": "submission_accepted", "round_id": round_id}
    )
    # 같은 세션 전체에는 제출 인원 수만 갱신
    await broadcast_submission_progress(round_.session_id, round_id, total)
