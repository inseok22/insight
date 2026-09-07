import json

from fastapi import APIRouter, Depends, Query, WebSocket, status
from fastapi.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.dependencies.features import require_feature
from app.core.security import TokenError, decode_access_token
from app.schemas.config import TerminalTargetResponse
from app.services.terminal_service import PROMPT, handle_command, initial_banner

router = APIRouter(tags=["terminal"])
settings = get_settings()


@router.get("/terminals/targets", response_model=list[TerminalTargetResponse], dependencies=[Depends(require_feature("terminal"))])
def read_terminal_targets() -> list[TerminalTargetResponse]:
    return [
        TerminalTargetResponse(
            key=key,
            name=key.replace("-", " ").title(),
            ws_path=f"/api/v1/ws/term/{key}",
        )
        for key in settings.terminal_targets_list
    ]


@router.websocket("/ws/term/{target_key}")
async def terminal_websocket(
    websocket: WebSocket,
    target_key: str,
    token: str | None = Query(default=None),
) -> None:
    if not get_settings().terminal_enabled or target_key not in settings.terminal_targets_list:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
    except TokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    username = payload.get("sub")
    if not username:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await websocket.send_text(initial_banner(target_key, username))

    buffer = ""

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            if msg_type == "resize":
                continue
            if msg_type != "data":
                continue

            chunk = str(message.get("data", ""))
            if not chunk:
                continue

            await websocket.send_text(chunk)
            buffer += chunk

            if "\r" in chunk or "\n" in chunk:
                command = buffer.replace("\r", "").replace("\n", "")
                response, should_close = handle_command(command, target_key, username)
                await websocket.send_text(response)
                buffer = ""
                if should_close:
                    await websocket.close(code=1000)
                    break
            elif len(buffer) > 512:
                buffer = ""
                await websocket.send_text(f"\r\n입력이 너무 깁니다.\r\n{PROMPT}")
    except WebSocketDisconnect:
        return
