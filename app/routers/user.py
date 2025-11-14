from aiogram import Router, types
from app.config import config
from app.storage.models import Message
from sqlalchemy import update, select
from app.storage.repo import save_message
from app.deps import SessionLocal, bot
from app.notifications import send_to_user_ws
from datetime import datetime

router = Router()


@router.message()
async def save_user_message(message: types.Message):
    async with SessionLocal() as session:

        media_type = None
        file_id = None
        text = message.text or ""

        # === PHOTO ===
        if message.photo:
            media_type = "photo"
            file_id = message.photo[-1].file_id

        # === VIDEO ===
        elif message.video:
            media_type = "video"
            file_id = message.video.file_id
            text = message.caption or ""

        # === DOCUMENT ===
        elif message.document:
            media_type = "document"
            file_id = message.document.file_id
            text = message.caption or ""

        # === VOICE ===
        elif message.voice:
            media_type = "voice"
            file_id = message.voice.file_id
            text = message.caption or ""

        # === AUDIO ===
        elif message.audio:
            media_type = "audio"
            file_id = message.audio.file_id
            text = message.caption or ""

        # === SAVE TO DB (ОБЯЗАТЕЛЬНО file_id, НЕ file_path!) ===
        db_msg = await save_message(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=text,
            tg_message_id=message.message_id,
            media_type=media_type,
            file_id=file_id,  # <-- сохраняем только file_id!
            status="delivered"
        )

        # Помечаем сообщения админа как прочитанные
        await session.execute(
            update(Message)
            .where(
                Message.user_id == message.from_user.id,
                Message.username == config.ADMIN_NAME,
                Message.status != "read"
            )
            .values(status="read")
        )
        await session.commit()

        # Список только что прочитанных
        res = await session.execute(
            select(Message.id)
            .where(
                Message.user_id == message.from_user.id,
                Message.username == config.ADMIN_NAME,
                Message.status == "read"
            )
        )
        read_ids = [row[0] for row in res.all()]

    # === PUSH WS ===
    payload = {
        "action": "message",
        "from": "user",
        "username": message.from_user.username or "user",
        "text": text,
        "created_at": datetime.utcnow().isoformat(),
        "status": "delivered",
        "id": db_msg.id,
    }

    if media_type:
        payload["media_type"] = media_type
        payload["file_id"] = file_id   # <-- отправляем file_id, НЕ file_path!

    # отправляем в вебчат
    try:
        await send_to_user_ws(message.from_user.id, payload)
    except Exception as e:
        print("[user_ws_push] error:", e)

    # отправляем обновления статусов read
    for mid in read_ids:
        try:
            await send_to_user_ws(
                message.from_user.id,
                {"action": "status_update", "msg_id": mid, "status": "read"},
            )
        except Exception as e:
            print("[status_update_ws] error:", e)
