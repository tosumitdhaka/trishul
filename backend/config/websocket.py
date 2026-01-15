"""
WebSocket manager for real-time updates
"""

import json
from typing import Dict, List

from fastapi import WebSocket

from utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manage WebSocket connections
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept new connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        self.active_connections.remove(websocket)
        # Remove from all subscriptions
        for topic in self.subscriptions:
            if websocket in self.subscriptions[topic]:
                self.subscriptions[topic].remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific connection"""
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        """Broadcast to all connections"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Connection might be closed
                pass

    async def publish(self, topic: str, message: dict):
        """Publish message to topic subscribers"""
        if topic in self.subscriptions:
            message_str = json.dumps({"topic": topic, "data": message})
            for connection in self.subscriptions[topic]:
                try:
                    await connection.send_text(message_str)
                except:
                    pass

    def subscribe(self, topic: str, websocket: WebSocket):
        """Subscribe to a topic"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if websocket not in self.subscriptions[topic]:
            self.subscriptions[topic].append(websocket)
            logger.info(f"WebSocket subscribed to topic: {topic}")

    def unsubscribe(self, topic: str, websocket: WebSocket):
        """Unsubscribe from a topic"""
        if topic in self.subscriptions and websocket in self.subscriptions[topic]:
            self.subscriptions[topic].remove(websocket)
            logger.info(f"WebSocket unsubscribed from topic: {topic}")


# Global manager instance
manager = ConnectionManager()
