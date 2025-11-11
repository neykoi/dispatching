from pydantic_settings import BaseSettings

class Config(BaseSettings):
    BOT_TOKEN: str
    ADMIN_PASSWORD: str = "admin"
    DB_URL: str = "sqlite+aiosqlite:///./bot.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

config = Config()
