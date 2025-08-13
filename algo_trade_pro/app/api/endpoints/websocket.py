"""
app/api/endpoints/websocket.py

WebSocket endpoint for algo_trade_pro platform.
Manages real-time client connections for live dashboards, trade notifications, or streaming stats.
Integrates with ConnectionManager and can broadcast events to all dashboard clients.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.connection_manager import connection_manager
from app.services.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Accepts and manages a single client WebSocket connection.
    Streams live data/events to client and removes client on disconnect.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Optionally: Receive and process messages from client (e.g., dashboard commands)
            data = await websocket.receive_json()
            logger.info(f"Received via WebSocket: {data}")
            # (Optional) Echo: await connection_manager.send_personal_message({"echo": data}, websocket)
            # (Optional) Broadcast to all:
            # await connection_manager.broadcast({"event": "user_message", "data": data})

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected.")

    except Exception as e:
        connection_manager.disconnect(websocket)
        logger.error(f"WebSocket error: {e}")

