"""Telemetry WebSocket API router."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..daemons.telemetry import TelemetryWebSocketManager

router = APIRouter(tags=["telemetry"])

ws_manager = TelemetryWebSocketManager()


@router.websocket("/telemetry/ws")
async def telemetry_websocket(websocket: WebSocket):
    await websocket.accept()
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"Telemetry WebSocket error: {e}")
        ws_manager.disconnect(websocket)


def get_ws_manager() -> TelemetryWebSocketManager:
    return ws_manager
