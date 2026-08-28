"""
ATOA WebSocket Telemetry Broadcaster Router.
Maintains active WebSocket connections from frontend visualizers (nvss) and broadcasts real-time event envelopes.
"""

import json
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.app.models import EventEnvelope, EventType

router = APIRouter(prefix="/v1/events", tags=["events"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts typed events."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_type: EventType, data: Dict[str, Any]):
        """Creates an EventEnvelope and sends it to all connected frontend clients."""
        envelope = EventEnvelope(
            event_type=event_type,
            data=data
        )
        message = envelope.model_dump_json()
        
        # Broadcast to all active clients safely
        stale_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale_connections.append(connection)
                
        for stale in stale_connections:
            self.disconnect(stale)


# Global singleton connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time observer telemetry.
    Clients connect to ws://localhost:8000/v1/events/ws to receive live event streams.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial connection handshake
        await websocket.send_text(json.dumps({
            "event_type": "CONNECTED",
            "message": "ATOA Real-Time Telemetry Stream Connected"
        }))
        
        # Keep connection open and listen for client heartbeats/messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
