from sqlalchemy import Column, Float, Integer, String, UniqueConstraint

from app.core.database import Base


class UsageCounter(Base):
    """Monthly usage per user and metric (documents, voice_chars, quiz_questions, llm_tokens…).
    user_key is the user id as text, or "anon" for unauthenticated calls."""
    __tablename__ = "edu_usage_counters"
    __table_args__ = (UniqueConstraint("user_key", "metric", "period", name="uq_usage_user_metric_period"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_key = Column(String(64), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    period = Column(String(7), nullable=False)      # "2026-11"
    amount = Column(Float, nullable=False, default=0)
