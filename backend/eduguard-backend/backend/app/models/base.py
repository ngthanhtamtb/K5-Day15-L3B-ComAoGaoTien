from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.inspection import inspect
from app.core.database import Base
from sqlalchemy.ext.declarative import as_declarative, declared_attr


class BaseModel(Base):
    __abstract__ = True
    __name__: str

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_active = Column(Boolean, index=True, default=True)
    created_at = Column(DateTime(timezone=True), index=True, default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=True, default=False)
    deleted_at = Column(DateTime, nullable=True, default=None)

    class Config:
        from_attributes = True

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
