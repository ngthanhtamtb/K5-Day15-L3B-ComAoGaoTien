from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from app.core.db_types import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import BaseModel as SQLBaseModel

class Notification(SQLBaseModel):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, default="info")
    data = Column(JSONB, default={})
    is_read = Column(Boolean, default=False)

    user = relationship("User", back_populates="notifications")
