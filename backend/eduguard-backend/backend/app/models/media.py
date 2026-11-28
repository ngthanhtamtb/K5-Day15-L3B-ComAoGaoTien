from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from app.core.db_types import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import BaseModel as SQLBaseModel


class MediaAsset(SQLBaseModel):
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    slide_metadata = Column(JSONB, default={})

    is_ai_generated = Column(Boolean, default=False)
    generation_prompt = Column(Text)

    user = relationship("User")


class AIGenerationJob(SQLBaseModel):
    __tablename__ = "ai_generation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, default="pending")
    input_data = Column(JSONB, default={})
    output_data = Column(JSONB, default={})
    error_message = Column(Text)
    completed_at = Column(DateTime)

    user = relationship("User")
