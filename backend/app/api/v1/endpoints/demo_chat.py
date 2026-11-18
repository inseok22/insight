from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies.auth import ActiveAdminDep
from app.dependencies.features import require_feature
from app.schemas.chat import ChatMessage, ChatStop
from app.services.demo_chat import ChatService

router = APIRouter(prefix="/chat", tags=["demo-chat"], dependencies=[Depends(require_feature("demo_chat"))])


def service_for(request: Request) -> ChatService:
    service = getattr(request.app.state, "demo_chat", None)
    if service is None:
        raise HTTPException(503, "시연 채팅을 사용할 수 없습니다.")
    return service


class ChatStreamingResponse(StreamingResponse):
    """Cleanup even if sending response headers/body fails before iteration starts."""
    def __init__(self, service, session, run):
        super().__init__(service.events(run), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no",
        })
        self.service, self.session, self.run = service, session, run

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Starlette cancels its task group on a browser disconnect. Shield the
            # upstream close and observation finalizers from that cancellation.
            with anyio.CancelScope(shield=True):
                await self.service.disconnect(self.session, self.run)


@router.post("/sessions")
async def new_session(request: Request, admin: ActiveAdminDep):
    session = service_for(request).create_session(admin.id)
    return {"session_id": session.id}


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: UUID, payload: ChatMessage, request: Request, admin: ActiveAdminDep):
    service = service_for(request)
    session = service.owned_session(str(session_id), admin.id)
    run = service.begin(session, str(payload.request_id), payload.message)
    return ChatStreamingResponse(service, session, run)


@router.post("/sessions/{session_id}/stop")
async def stop_message(session_id: UUID, payload: ChatStop, request: Request, admin: ActiveAdminDep):
    service = service_for(request)
    session = service.owned_session(str(session_id), admin.id)
    return {"status": service.stop(session, str(payload.request_id))}
