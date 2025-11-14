from typing import Dict, Optional
from fastapi import WebSocket
import json
import asyncio

# Активные соединения WebSocket (user_id → WebSocket)
active_connections: Dict[int, WebSocket] = {}

# Lock создаём позже, когда появится event loop
lock: Optional[asyncio.Lock] = None


async def ensure_lock():
    """Создаёт Lock при первом использовании (если его ещё нет)."""
    global lock
    if lock is None:
        lock = asyncio.Lock()


async def register_ws(user_id: int, websocket: WebSocket):
    """Регистрирует новое WebSocket-соединение."""
    await ensure_lock()
    async with lock:
        active_connections[user_id] = websocket


async def unregister_ws(user_id: int):
    """Удаляет WebSocket-соединение (при обрыве или закрытии)."""
    await ensure_lock()
    async with lock:
        active_connections.pop(user_id, None)


async def send_to_user_ws(user_id: int, message: dict):
    """Отправить сообщение в активное соединение конкретного user_id."""
    await ensure_lock()
    ws = active_connections.get(user_id)
    if not ws:
        return False
    try:
        await ws.send_text(json.dumps(message))
        return True
    except Exception:
        # Если соединение умерло — удалить
        await unregister_ws(user_id)
        return False


async def broadcast(message: dict):
    """Отправить сообщение всем активным соединениям."""
    await ensure_lock()
    text = json.dumps(message)
    dead_users = []
    async with lock:
        for uid, ws in active_connections.items():
            try:
                await ws.send_text(text)
            except Exception:
                dead_users.append(uid)
        for uid in dead_users:
            active_connections.pop(uid, None)
