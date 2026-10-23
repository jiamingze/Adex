"""Only the narrowly scoped speech WebSocket is exposed by the gateway."""

from uuid import UUID
from fastapi import APIRouter, WebSocket
from adex_tools.dependencies import core
from adex_tools.speech.service import relay

router = APIRouter()


@router.websocket("/speech-ws/{session_id}")
async def speech(socket: WebSocket, session_id: UUID):
    await socket.accept()
    await relay(socket, core, session_id)
