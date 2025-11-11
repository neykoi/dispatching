from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    username = Column(String)
    text = Column(Text)
    tg_message_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
