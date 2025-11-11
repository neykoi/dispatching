from aiogram import Bot
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import config

bot = Bot(token=config.BOT_TOKEN)
engine = create_async_engine(config.DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
