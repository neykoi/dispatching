from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    username = Column(String)
    text = Column(Text)
    tg_message_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="sent")  # sent | delivered | read | deleted
    file_id = Column(String, nullable=True)
    media_type = Column(String, nullable=True)  # photo, video, document, voice
