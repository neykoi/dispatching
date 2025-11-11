from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.models import Message

async def save_message(session: AsyncSession, user_id: int, username: str, text: str, tg_message_id: int):
    m = Message(user_id=user_id, username=username, text=text, tg_message_id=tg_message_id)
    session.add(m)
    await session.commit()

async def get_all_users(session: AsyncSession):
    res = await session.execute(select(Message.user_id, Message.username).distinct())
    return res.all()

async def get_user_messages(session: AsyncSession, user_id: int):
    res = await session.execute(select(Message).where(Message.user_id == user_id))
    return res.scalars().all()

async def delete_user_messages(session: AsyncSession, user_id: int):
    await session.execute(delete(Message).where(Message.user_id == user_id))
    await session.commit()

async def delete_single_message(session: AsyncSession, msg_id: int):
    await session.execute(delete(Message).where(Message.id == msg_id))
    await session.commit()
