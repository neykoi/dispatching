from aiogram import Router, types
from aiogram.filters import CommandStart
from app.deps import SessionLocal
from app.storage.repo import save_message

router = Router()

@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("👋 Привет! Напиши сюда сообщение, оно попадёт в поддержку.")

@router.message()
async def save_user_message(message: types.Message):
    async with SessionLocal() as session:
        await save_message(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=message.text or "",
            tg_message_id=message.message_id
        )
    from app.notifications import broadcast
    await broadcast({"type":"message","user_id":message.from_user.id,"username":message.from_user.username or "","text":message.text or "","from_admin":False})
    await message.answer("✅ Сообщение сохранено. С вами свяжется админ.")
