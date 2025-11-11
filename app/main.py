import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import asyncio
import logging
from aiogram import Dispatcher
from app.deps import bot, engine
from app.storage.models import Base
from app.routers import user
from web.admin_panel import app as web_app
import uvicorn

logging.basicConfig(level=logging.INFO)

async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def run_bot():
    dp = Dispatcher()
    dp.include_router(user.router)
    await on_startup()
    await dp.start_polling(bot)

async def run_web():
    config = uvicorn.Config(web_app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_web())

if __name__ == "__main__":
    asyncio.run(main())
