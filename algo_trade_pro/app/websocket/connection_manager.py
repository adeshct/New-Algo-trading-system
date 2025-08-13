"""
WebSocket connection manager for real-time client communications.
Handles multiple client connections and broadcasts updates.
"""

from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.services.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket client connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket client connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client} (Total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket client connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected: {websocket.client} (Total: {len(self.active_connections)})")

    async def send_personal_message(self, message: Any, websocket: WebSocket):
        """Send a message to a specific WebSocket client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Any):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: JSON-serializable object (strategy updates, trade notifications, etc.)
        """
        if not self.active_connections:
            return
        
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast failed for client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for dc in disconnected:
            self.disconnect(dc)

    def get_connections_count(self) -> int:
        """Get the number of active WebSocket connections."""
        return len(self.active_connections)

# Singleton instance for global use
connection_manager = ConnectionManager()