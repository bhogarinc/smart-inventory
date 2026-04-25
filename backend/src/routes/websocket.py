"""
WebSocket routes for real-time inventory updates.
"""
import json
from typing import Dict, Set

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger()

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, channel: str = "general"):
        await websocket.accept()
        self.all_connections.add(websocket)
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        logger.info("WebSocket connected", channel=channel)

    def disconnect(self, websocket: WebSocket, channel: str = "general"):
        self.all_connections.discard(websocket)
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        logger.info("WebSocket disconnected", channel=channel)

    async def broadcast(self, message: dict, channel: str = "general"):
        """Broadcast message to all connections in a channel."""
        if channel in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)
            for conn in disconnected:
                self.disconnect(conn, channel)

    async def broadcast_all(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        for connection in self.all_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.all_connections.discard(conn)


manager = ConnectionManager()


@router.websocket("/inventory")
async def websocket_inventory(websocket: WebSocket):
    """WebSocket endpoint for real-time inventory updates."""
    await manager.connect(websocket, "inventory")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle subscription requests
                if message.get("type") == "subscribe":
                    channel = message.get("channel", "inventory")
                    if channel not in manager.active_connections:
                        manager.active_connections[channel] = set()
                    manager.active_connections[channel].add(websocket)
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": channel,
                    })
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "inventory")


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert notifications."""
    await manager.connect(websocket, "alerts")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager
