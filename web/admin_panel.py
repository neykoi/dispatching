from fastapi import APIRouter, Request, WebSocket, UploadFile, File, Form, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, Response
from jinja2 import Environment, FileSystemLoader
from app.storage.repo import get_all_users, save_message, get_user_messages, update_message_status, get_message_by_id
from app.config import config
from app import config as app_config
from app.auth import create_token, verify_token
import json, os, asyncio, aiohttp, mimetypes
from typing import List
from uuid import uuid4
from app.deps import SessionLocal, bot
from app.notifications import register_ws, unregister_ws, send_to_user_ws
from datetime import datetime
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

env = Environment(loader=FileSystemLoader("web/templates"))
router = APIRouter()

CACHE_FILE = "web/.admin_cache.json"


def read_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_cache(d):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f)


def is_authed(request: Request):
    token = request.cookies.get("admin_token")
    if token and verify_token(token):
        return True
    cache = read_cache()
    token = cache.get("token")
    if token and verify_token(token):
        return True
    return False


# ------------------ Media proxy (Telegram) ------------------

from fastapi.responses import Response, HTMLResponse
import aiohttp

@router.get("/media_proxy/{file_id:path}")
async def media_proxy(file_id: str):
    try:
        # --- 1) Определяем file_path ---
        if "/" in file_id:
            # старые записи содержат готовый file_path
            file_path = file_id
        else:
            # новый формат — это Telegram FILE_ID
            tg_file = await bot.get_file(file_id)
            file_path = tg_file.file_path

        url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file_path}"

        # --- 2) Качаем файл полностью ---
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return HTMLResponse("File not found", status_code=404)

                data = await resp.read()

                return Response(
                    content=data,
                    media_type=resp.headers.get("Content-Type", "application/octet-stream"),
                )

    except Exception as e:
        print("[media_proxy ERROR]:", e)
        return HTMLResponse("Error fetching media", status_code=500)

# ------------------ Pages ------------------

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("admin_token")
    cache = read_cache()
    if not token and cache.get("token") and verify_token(cache.get("token")):
        token = cache.get("token")
    if not token or not verify_token(token):
        token = create_token()
        cache["token"] = token
        write_cache(cache)

    async with SessionLocal() as session:
        users = await get_all_users(session)
        users = [u for u in users if (u[1] or "").lower() != (config.ADMIN_NAME or "admin").lower()]

    tpl = env.get_template("index.html")
    resp = HTMLResponse(tpl.render(users=[(u[0], u[1]) for u in users]))
    resp.set_cookie("admin_token", token, httponly=True, max_age=60 * 60 * 8)
    return resp


@router.get("/dialog/{user_id}", response_class=HTMLResponse)
async def dialog(request: Request, user_id: int):
    if not is_authed(request):
        return RedirectResponse("/", status_code=302)

    async with SessionLocal() as session:
        messages = await get_user_messages(session, user_id)

    tpl = env.get_template("dialog.html")
    msgs = []
    for m in messages:
        msgs.append(
            {
                "id": m.id,
                "username": m.username,
                "text": m.text,
                "created_at": (
                    m.created_at.isoformat() if hasattr(m.created_at, "isoformat") else str(m.created_at)
                ),
                "status": getattr(m, "status", "sent"),
                "file_id": getattr(m, "file_id", None),
                "media_type": getattr(m, "media_type", None),
            }
        )

    username = None
    for m in messages:
        if m.username and m.username != config.ADMIN_NAME:
            username = m.username
            break

    return HTMLResponse(
        tpl.render(
            user_id=user_id,
            username=username,
            messages=msgs,
            config=app_config,
        )
    )


# ------------------ Delete single message ------------------

@router.post("/delete_msg")
async def delete_msg(user_id: int = Form(...), msg_id: int = Form(...)):
    async with SessionLocal() as session:
        msg = await get_message_by_id(session, int(msg_id))
        if not msg:
            return JSONResponse({"ok": False, "error": "not_found"}, status_code=200)

        try:
            if msg.tg_message_id:
                await bot.delete_message(user_id, msg.tg_message_id)
        except Exception as e:
            print(f"[delete_msg] Telegram delete failed: {e}")

        msg.status = "deleted"
        await session.commit()

        await send_to_user_ws(user_id, {
            "action": "status_update",
            "msg_id": msg.id,
            "status": "deleted",
        })

    return JSONResponse({"ok": True, "deleted": True})


# ------------------ WebSocket ------------------

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    await register_ws(user_id, websocket)

    async def update_status(msg_id: int, new_status: str):
        async with SessionLocal() as session:
            await update_message_status(session, msg_id, new_status)
        await send_to_user_ws(user_id, {
            "action": "status_update",
            "msg_id": msg_id,
            "status": new_status,
        })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "send":
                raw_text = data.get("text", "") or ""
                text = raw_text.strip()

                media_type = data.get("media_type")
                file_id = data.get("file_id")

                if not text and not file_id:
                    continue

                async with SessionLocal() as session:
                    msg = await save_message(
                        session,
                        user_id=user_id,
                        username=config.ADMIN_NAME or "admin",
                        text=text,
                        tg_message_id=0,
                        media_type=media_type if file_id else None,
                        file_id=file_id if file_id else None,
                        status="sent",
                    )

                payload = {
                    "action": "message",
                    "from": "admin",
                    "username": config.ADMIN_NAME or "admin",
                    "text": text,
                    "created_at": datetime.utcnow().isoformat(),
                    "id": msg.id,
                    "status": "sent",
                }
                if file_id and media_type:
                    payload.update({"media_type": media_type, "file_id": file_id})

                await send_to_user_ws(user_id, payload)

                try:
                    if file_id and media_type:
                        caption = text or None
                        send_kwargs = {"caption": caption} if caption else {}
                        if media_type == "photo":
                            sent = await bot.send_photo(int(user_id), file_id, **send_kwargs)
                            new_file_id = sent.photo[-1].file_id if sent.photo else file_id
                        elif media_type == "video":
                            sent = await bot.send_video(int(user_id), file_id, **send_kwargs)
                            new_file_id = sent.video.file_id if getattr(sent, "video", None) else file_id
                        elif media_type == "voice":
                            sent = await bot.send_voice(int(user_id), file_id, **send_kwargs)
                            voice_obj = getattr(sent, "voice", None)
                            new_file_id = voice_obj.file_id if voice_obj else file_id
                        elif media_type == "audio":
                            sent = await bot.send_audio(int(user_id), file_id, **send_kwargs)
                            audio_obj = getattr(sent, "audio", None)
                            new_file_id = audio_obj.file_id if audio_obj else file_id
                        else:
                            sent = await bot.send_document(int(user_id), file_id, **send_kwargs)
                            doc_obj = getattr(sent, "document", None)
                            new_file_id = doc_obj.file_id if doc_obj else file_id

                        tg_id = getattr(sent, "message_id", 0)

                        async with SessionLocal() as session:
                            db_msg = await get_message_by_id(session, msg.id)
                            if db_msg:
                                db_msg.tg_message_id = tg_id
                                db_msg.media_type = media_type
                                db_msg.file_id = new_file_id
                                await session.commit()
                    else:
                        sent = await bot.send_message(int(user_id), text)
                        tg_id = getattr(sent, "message_id", 0)

                        async with SessionLocal() as session:
                            db_msg = await get_message_by_id(session, msg.id)
                            if db_msg:
                                db_msg.tg_message_id = tg_id
                                await session.commit()

                    await update_status(msg.id, "delivered")

                except Exception as e:
                    print(f"[ERROR] Telegram send: {e}")
                    await update_status(msg.id, "failed")

            elif action == "clear_history":
                try:
                    async with SessionLocal() as session:
                        msgs = await get_user_messages(session, user_id)

                        for msg in msgs:
                            try:
                                if msg.tg_message_id:
                                    await bot.delete_message(user_id, msg.tg_message_id)
                            except Exception as e:
                                print(f"[clear_history] Telegram delete failed: {e}")

                            msg.status = "deleted"

                        await session.commit()

                    # отправляем клиенту обновления статусов
                    for msg in msgs:
                        await send_to_user_ws(user_id, {
                            "action": "status_update",
                            "msg_id": msg.id,
                            "status": "deleted",
                        })

                except Exception as e:
                    print(f"[clear_history] error: {e}")

    except WebSocketDisconnect:
        await unregister_ws(user_id)


# ------------------ Upload admin files ------------------

@router.post("/upload_admin_file")
async def upload_admin_file(
    user_id: int = Form(...),
    files: List[UploadFile] = File(...),
    album: bool = Form(False),
):
    os.makedirs("media", exist_ok=True)
    saved_files = []
    temp_items = []

    def detect_media_type(upload: UploadFile, file_path: str) -> str:
        mime = upload.content_type or mimetypes.guess_type(upload.filename or "")[0]
        if not mime:
            mime = mimetypes.guess_type(file_path)[0]

        if mime and mime.startswith("image/"):
            return "photo"
        if mime and mime.startswith("video/"):
            return "video"
        if mime and mime.startswith("audio/"):
            return "voice" if "ogg" in mime else "audio"
        return "document"

    for f in files:
        ext = os.path.splitext(f.filename or "")[1]
        tmp_name = f"{uuid4().hex}{ext}"
        file_path = os.path.join("media", tmp_name)
        with open(file_path, "wb") as out:
            out.write(await f.read())

        media_type = detect_media_type(f, file_path)
        temp_items.append({
            "path": file_path,
            "media_type": media_type,
        })

    async def persist_and_broadcast(media_type: str, file_id: str, tg_id: int):
        async with SessionLocal() as session:
            msg = await save_message(
                session,
                user_id=user_id,
                username=config.ADMIN_NAME or "admin",
                text="",
                tg_message_id=tg_id,
                media_type=media_type,
                file_id=file_id,
                status="delivered",
            )

        await send_to_user_ws(
            user_id,
            {
                "action": "message",
                "from": "admin",
                "username": config.ADMIN_NAME or "admin",
                "media_type": media_type,
                "file_id": file_id,
                "text": "",
                "created_at": datetime.utcnow().isoformat(),
                "id": msg.id,
                "status": "delivered",
            },
        )

        saved_files.append({"id": file_id, "type": media_type})

    async def send_single(item):
        input_file = FSInputFile(item["path"])
        media_type = item["media_type"]

        if media_type == "photo":
            sent = await bot.send_photo(user_id, input_file)
            file_id = sent.photo[-1].file_id if sent.photo else ""
        elif media_type == "video":
            sent = await bot.send_video(user_id, input_file)
            file_id = sent.video.file_id if getattr(sent, "video", None) else ""
        elif media_type == "voice":
            sent = await bot.send_voice(user_id, input_file)
            voice_obj = getattr(sent, "voice", None)
            file_id = voice_obj.file_id if voice_obj else ""
        elif media_type == "audio":
            sent = await bot.send_audio(user_id, input_file)
            audio_obj = getattr(sent, "audio", None)
            file_id = audio_obj.file_id if audio_obj else ""
        else:
            sent = await bot.send_document(user_id, input_file)
            doc_obj = getattr(sent, "document", None)
            file_id = doc_obj.file_id if doc_obj else ""

        await persist_and_broadcast(media_type, file_id, sent.message_id)

        try:
            os.remove(item["path"])
        except OSError:
            pass

    async def send_album_group(chunk):
        media_inputs = []
        for entry in chunk:
            fs_file = FSInputFile(entry["path"])
            if entry["media_type"] == "photo":
                media_inputs.append(InputMediaPhoto(media=fs_file))
            else:
                media_inputs.append(InputMediaVideo(media=fs_file))

        sent_messages = await bot.send_media_group(user_id, media_inputs)
        for sent, entry in zip(sent_messages, chunk):
            if entry["media_type"] == "photo" and sent.photo:
                file_id = sent.photo[-1].file_id
            elif entry["media_type"] == "video" and getattr(sent, "video", None):
                file_id = sent.video.file_id
            else:
                file_id = ""

            await persist_and_broadcast(entry["media_type"], file_id, sent.message_id)

            try:
                os.remove(entry["path"])
            except OSError:
                pass

    can_send_album = (
        album
        and len(temp_items) > 1
        and all(item["media_type"] in ("photo", "video") for item in temp_items)
    )

    if can_send_album:
        for i in range(0, len(temp_items), 10):
            chunk = temp_items[i : i + 10]
            if len(chunk) > 1:
                await send_album_group(chunk)
            else:
                await send_single(chunk[0])
    else:
        for item in temp_items:
            await send_single(item)

    return {"ok": True, "files": saved_files}

