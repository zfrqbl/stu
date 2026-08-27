"""TelemetryDaemon: collects and broadcasts system telemetry."""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from .manager import Daemon


class TelemetryWebSocketManager:
    """Manages WebSocket connections for telemetry broadcast."""

    def __init__(self):
        self._connections: set = set()

    async def connect(self, websocket):
        self._connections.add(websocket)
        logger.debug(f"Telemetry WebSocket connected. Total: {len(self._connections)}")

    def disconnect(self, websocket):
        self._connections.discard(websocket)
        logger.debug(f"Telemetry WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._connections:
            return

        payload = json.dumps(message)
        stale = set()

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.add(ws)

        for ws in stale:
            self._connections.discard(ws)

    @property
    def active_connections(self) -> int:
        return len(self._connections)


class TelemetryDaemon(Daemon):
    """Collects system metrics and broadcasts to connected clients."""

    def __init__(
        self,
        interval_seconds: float,
        enabled: bool,
        ws_manager: TelemetryWebSocketManager,
        state_manager=None,
        tool_catalog=None,
        mcp_connection_manager=None,
        memory_service=None,
        daemon_manager=None,
    ):
        super().__init__("telemetry", interval_seconds, enabled)
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        self.tool_catalog = tool_catalog
        self.mcp_connection_manager = mcp_connection_manager
        self.memory_service = memory_service
        self.daemon_manager = daemon_manager
        self._total_broadcasts = 0

    async def tick(self) -> None:
        payload = self._collect_metrics()
        await self.ws_manager.broadcast(payload)
        self._total_broadcasts += 1

    def _collect_metrics(self) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "type": "telemetry_update",
            "timestamp": time.time(),
            "daemon_status": [],
            "loop_state": None,
            "tool_stats": {},
            "mcp_stats": {},
            "memory_stats": {},
            "ws_clients": self.ws_manager.active_connections,
            "total_broadcasts": self._total_broadcasts,
        }

        if self.daemon_manager:
            metrics["daemon_status"] = self.daemon_manager.get_status()

        if self.state_manager:
            try:
                state = self.state_manager.load_state()
                if state:
                    metrics["loop_state"] = {
                        "status": state.status.value,
                        "phase": state.current_phase.value,
                        "project_id": state.project_id,
                        "goal": state.goal[:100] if state.goal else "",
                    }
            except Exception:
                pass

        if self.tool_catalog:
            try:
                tools = self.tool_catalog.list_tools(include_disabled=False)
                native_count = sum(1 for t in tools if t.kind.value == "native")
                mcp_count = sum(1 for t in tools if t.kind.value == "mcp")
                metrics["tool_stats"] = {
                    "total": len(tools),
                    "native": native_count,
                    "mcp": mcp_count,
                }
            except Exception:
                pass

        if self.mcp_connection_manager:
            try:
                connections = self.mcp_connection_manager.get_all_connections()
                connected = sum(1 for c in connections if c.status == "connected")
                total_tools = sum(c.tools_count for c in connections)
                metrics["mcp_stats"] = {
                    "servers_total": len(connections),
                    "servers_connected": connected,
                    "total_tools": total_tools,
                }
            except Exception:
                pass

        if self.memory_service:
            try:
                # Basic memory stats (count of entries for default project)
                entries = self.memory_service.list_memories("default", query=None)
                metrics["memory_stats"] = {
                    "entry_count": len(entries),
                }
            except Exception:
                pass

        return metrics
