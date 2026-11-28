import uuid
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.core.db_types import JSONB, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import BaseModel as SQLBaseModel


class User(SQLBaseModel):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    avatar_url = Column(String)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    # admin | giang_vien | bien_tap | nguoi_dung  (see app/edu/billing). Existing PostgreSQL DBs:
    #   ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'giang_vien';
    role = Column(String, default="giang_vien", nullable=True)
    subscription_type = Column(String, default="free")      # mapped to a plan in config/plans.yaml
    subscription_expires = Column(DateTime)
    usage_stats = Column(JSONB, default={})

    # Relationships
    presentations = relationship("Presentation", back_populates="owner")
    templates = relationship("Template", foreign_keys="Template.created_by_user_id", back_populates="creator")
    notifications = relationship("Notification", back_populates="user")
