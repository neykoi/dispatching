from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.models import Message

# =========================
#   СОХРАНЕНИЕ / ЗАГРУЗКА
# =========================

async def save_message(
    session: AsyncSession,
    user_id: int,
    username: str,
    text: str,
    tg_message_id: int,
    media_type: str = None,
    file_id: str = None,
    status: str = "sent"
):
    m = Message(
        user_id=user_id,
        username=username,
        text=text,
        tg_message_id=tg_message_id,
        media_type=media_type,
        file_id=file_id,
        status=status,
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def get_all_users(session: AsyncSession):
    """
    Получить всех пользователей, которые когда-либо писали.
    """
    res = await session.execute(select(Message.user_id, Message.username).distinct())
    return res.all()


async def get_user_messages(session: AsyncSession, user_id: int):
    """
    Получить все сообщения конкретного пользователя.
    """
    res = await session.execute(select(Message).where(Message.user_id == user_id))
    return res.scalars().all()

# =========================
#       УДАЛЕНИЕ (НОВАЯ ЛОГИКА)
# =========================

async def delete_user_messages(session: AsyncSession, user_id: int):
    """
    Пометить все сообщения пользователя как 'deleted' (не удаляя их из базы).
    """
    await session.execute(
        update(Message)
        .where(Message.user_id == user_id)
        .values(status="deleted")
    )
    await session.commit()


async def delete_single_message(session: AsyncSession, msg_id: int):
    """
    Пометить одно сообщение как 'deleted' (не удаляя текст).
    """
    await session.execute(
        update(Message)
        .where(Message.id == msg_id)
        .values(status="deleted")
    )
    await session.commit()

# =========================
#       ДОПОЛНИТЕЛЬНО
# =========================

async def get_message_by_id(session: AsyncSession, msg_id: int):
    """
    Получить одно сообщение по ID.
    """
    result = await session.execute(select(Message).where(Message.id == msg_id))
    return result.scalar_one_or_none()


async def update_message_status(session: AsyncSession, msg_id: int, new_status: str):
    """
    Обновить статус сообщения ('sent', 'delivered', 'read', 'deleted').
    """
    await session.execute(
        update(Message)
        .where(Message.id == msg_id)
        .values(status=new_status)
    )
    await session.commit()
