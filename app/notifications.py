from typing import List
from fastapi import WebSocket
import json

active_connections: List[WebSocket] = []

async def broadcast(message: dict):
    text = json.dumps(message)
    for ws in active_connections.copy():
        try:
            await ws.send_text(text)
        except Exception:
            try:
                active_connections.remove(ws)
            except Exception:
                pass
