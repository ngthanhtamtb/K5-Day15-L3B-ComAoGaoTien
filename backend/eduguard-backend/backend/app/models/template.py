import uuid
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, exists, and_
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.db_types import JSONB, UUID
from app.models.base import BaseModel as SQLBaseModel
from app.core.pptagent.types import PageScopeType


class Template(SQLBaseModel):
    __tablename__ = 'templates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=True, index=True)
    subject = Column(String(525), nullable=True)
    description = Column(Text, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    cover_url = Column(String, nullable=True)
    thumbnail_url = Column(JSONB, nullable=True)
    file_url = Column(Text, nullable=True)
    template_type = Column(String, nullable=True, default='user', index=True)
    template_category = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    approved_by_admin_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    status = Column(String, nullable=True, default='private', index=True)
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    is_approved = Column(Boolean, default=False, index=True)
    usage_count = Column(Integer, default=0, index=True)
    rejection_reason = Column(Text, nullable=True)
    tags = Column(JSONB, index=True)
    background = Column(JSONB, nullable=True)
    ext_info = Column(JSONB, nullable=True)
    gen_type = Column(String, nullable=True, index=True)
    view_count = Column(Integer, default=0, index=True)
    download_count = Column(Integer, default=0, index=True)
    like_count = Column(Integer, default=0, index=True)
    clone_count = Column(Integer, default=0, index=True)
    is_premium = Column(Boolean, default=False, index=True)
    price = Column(Float, default=0.0, index=True)
    slug = Column(String, unique=True, index=True)
    keywords = Column(JSONB, index=True)
    difficulty_level = Column(Integer, default=1)
    estimated_time = Column(Integer)
    approved_at = Column(DateTime(timezone=True), index=True)
    published_at = Column(DateTime(timezone=True), index=True)
    last_used_at = Column(DateTime(timezone=True), index=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_user_id], back_populates="templates")
    approver = relationship("User", foreign_keys=[approved_by_admin_id])
    pages = relationship("TemplatePage", back_populates="template", cascade="all, delete-orphan")
    reviews = relationship("TemplateReview", back_populates="template", cascade="all, delete-orphan")
    collections = relationship("TemplateCollection", secondary="template_collection_items", back_populates="templates")

    def is_like_and_is_favorite(self, db=None, user_id=None):
        if not user_id or not db:
            return {
                "is_favorite": False,
                "is_like": False
            }

        return {
            "is_favorite": db.query(
                exists().where(and_(
                    UserFavoriteTemplate.template_id == self.id,
                    UserFavoriteTemplate.user_id == user_id
                ))
            ).scalar(),
            "is_like": db.query(
                exists().where(and_(
                    TemplateLike.template_id == self.id,
                    TemplateLike.user_id == user_id
                ))
            ).scalar()
        }


class TemplatePage(SQLBaseModel):
    __tablename__ = 'template_pages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    approved_by_admin_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    page_scope = Column(String, default=PageScopeType.USER, nullable=True)
    page_type = Column(String, nullable=True)
    page_category = Column(String, nullable=True)
    page_section = Column(String, nullable=True)
    page_order = Column(Integer, nullable=True)
    page_name = Column(String(100), nullable=True)
    page_description = Column(Text, nullable=True)
    page_data = Column(JSONB, nullable=True)
    tags = Column(JSONB, nullable=True)
    background = Column(JSONB, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    preview_data = Column(JSONB, nullable=True)
    animation_count = Column(Integer, default=0, nullable=True)
    element_count = Column(Integer, default=0, nullable=True)
    usage_count = Column(Integer, default=0, nullable=True)
    text_filled_count = Column(Integer, default=0, nullable=True, index=True)
    last_used_at = Column(DateTime(timezone=True), index=True)

    template = relationship("Template", back_populates="pages")

    @property
    def is_system_page(self):
        return self.page_scope == PageScopeType.SYSTEM

    @property
    def is_standalone(self):
        return self.template_id is None

    def to_dict_summary(self, user_id=None):
        return {
            'id': str(self.id),
            'page_name': self.page_name,
            'page_type': self.page_type if self.page_type else None,
            'page_category': self.page_category if self.page_category else None,
            'page_section': self.page_section if self.page_section else None,
            'page_scope': self.page_scope,
            'is_standalone': self.is_standalone,
            'thumbnail_url': self.thumbnail_url,
            'tags': self.tags,
            'usage_count': self.usage_count if self.is_system_page else None
        }


class TemplateReview(SQLBaseModel):
    __tablename__ = 'template_reviews'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    rating = Column(Integer, nullable=False, index=True)
    review_text = Column(Text)
    is_verified_purchase = Column(Boolean, default=False, index=True)
    is_helpful_count = Column(Integer, default=0, index=True)

    # Relationships
    template = relationship("Template", back_populates="reviews")
    user = relationship("User")


class TemplateLike(SQLBaseModel):
    __tablename__ = 'template_likes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)


class TemplateUsage(SQLBaseModel):
    __tablename__ = 'template_usage'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    action_type = Column(String(50), nullable=False, index=True)  # 'view', 'download', 'clone'
    used_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user_agent = Column(String(500))
    ip_address = Column(String(45), index=True)
    referrer = Column(String(500))
    context_data = Column(JSONB, index=True)


class UserFavoriteTemplate(SQLBaseModel):
    __tablename__ = 'user_favorite_templates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)


class TemplateCollection(SQLBaseModel):
    __tablename__ = 'template_collections'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    cover_image_url = Column(String(500))
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    is_public = Column(Boolean, default=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    template_count = Column(Integer, default=0, index=True)
    view_count = Column(Integer, default=0, index=True)
    follow_count = Column(Integer, default=0, index=True)

    templates = relationship("Template", secondary="template_collection_items", back_populates="collections")


class TemplateCollectionItem(SQLBaseModel):
    __tablename__ = 'template_collection_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey('template_collections.id'), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)
    order_index = Column(Integer, default=0, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    added_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)


class TemplateReport(SQLBaseModel):
    __tablename__ = 'template_reports'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False, index=True)
    reported_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    reason = Column(String(100), nullable=False, index=True)  # 'copyright', 'inappropriate', 'spam'
    description = Column(Text)

    status = Column(String(50), default='pending', index=True)  # 'pending', 'resolved', 'dismissed'
    resolved_by_admin_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True), index=True)


class AnalyticsEvent(SQLBaseModel):
    __tablename__ = 'analytics_events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSONB, default={}, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    session_id = Column(String(100), index=True)

    user_agent = Column(String(500))
    ip_address = Column(String(45), index=True)
    referrer = Column(String(500))
