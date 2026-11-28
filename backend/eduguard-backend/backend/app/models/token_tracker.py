from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.db_types import JSONB
from sqlalchemy.sql import func
from app.models.base import BaseModel as SQLBaseModel


class TokenUsage(SQLBaseModel):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation_type = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    thoughts_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    operation_data = Column(JSONB, default={})
