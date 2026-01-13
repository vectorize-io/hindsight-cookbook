"""WebSocket connection manager."""

from fastapi import WebSocket
from typing import Dict, Set
import asyncio


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.delivery_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        # Accept with any origin (for cross-origin connections from dev frontend)
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Cancel any running delivery task
        if client_id in self.delivery_tasks:
            self.delivery_tasks[client_id].cancel()
            del self.delivery_tasks[client_id]

    async def send_event(self, client_id: str, event: dict):
        """Send an event to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(event)

    async def broadcast(self, event: dict):
        """Broadcast an event to all connected clients."""
        for websocket in self.active_connections.values():
            await websocket.send_json(event)

    def set_delivery_task(self, client_id: str, task: asyncio.Task):
        """Track a delivery task for a client."""
        self.delivery_tasks[client_id] = task

    def cancel_delivery(self, client_id: str) -> bool:
        """Cancel a running delivery task."""
        if client_id in self.delivery_tasks:
            self.delivery_tasks[client_id].cancel()
            del self.delivery_tasks[client_id]
            return True
        return False


# Global connection manager
manager = ConnectionManager()
