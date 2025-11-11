from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import config
from app.notifications import active_connections, broadcast
from app.deps import bot, SessionLocal
from app.storage.repo import save_message, get_user_messages
import json

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        token = websocket.cookies.get("admin_token")
        from app.auth import verify_token
        if not token or not verify_token(token):
            await websocket.send_text(json.dumps({"type":"error","detail":"auth_failed"}))
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return

    active_connections.append(websocket)
    try:
        await websocket.send_text(json.dumps({"type":"connected"}))
        while True:
            data = await websocket.receive_text()
            obj = json.loads(data)
            if obj.get("action") == "send":
                user_id = obj.get("user_id")
                text = obj.get("text")
                if user_id and text:
                    try:
                        await bot.send_message(chat_id=int(user_id), text=text)
                    except Exception as e:
                        await websocket.send_text(json.dumps({"type":"error","detail":str(e)}))
                        continue
                    async with SessionLocal() as session:
                        await save_message(session, user_id=int(user_id), username="admin", text=text, tg_message_id=0)
                    await broadcast({"type":"message","user_id":user_id,"username":"admin","text":text,"from_admin":True})
            elif obj.get("action") == "get_messages":
                user_id = obj.get("user_id")
                if user_id:
                    async with SessionLocal() as session:
                        msgs = await get_user_messages(session, int(user_id))
                        out = []
                        for m in msgs:
                            out.append({"id": m.id, "user_id": m.user_id, "username": m.username, "text": m.text, "created_at": str(m.created_at)})
                        await websocket.send_text(json.dumps({"type":"history","user_id":user_id,"messages":out}))
            else:
                await websocket.send_text(json.dumps({"type":"error","detail":"unknown_action"}))
    except WebSocketDisconnect:
        try:
            active_connections.remove(websocket)
        except Exception:
            pass
    except Exception:
        try:
            active_connections.remove(websocket)
        except Exception:
            pass
