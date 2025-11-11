from aiogram import Bot
from app.storage.repo import delete_user_messages, delete_single_message

async def delete_user_history(bot: Bot, session, user_id: int, messages):
    for msg in messages:
        try:
            await bot.delete_message(user_id, msg.tg_message_id)
        except Exception:
            pass
    await delete_user_messages(session, user_id)

async def delete_one(bot: Bot, session, user_id: int, msg):
    try:
        await bot.delete_message(user_id, msg.tg_message_id)
    except Exception:
        pass
    await delete_single_message(session, msg.id)
