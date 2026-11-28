import uuid
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, Float,
    ForeignKey, Enum as SQLAEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.db_types import JSONB, UUID
from app.core.pptagent.types import (
    PresentationStatusType, CollaboratorRoleType, CommentStatusType
)
from app.models.base import BaseModel as SQLBaseModel


class Presentation(SQLBaseModel):
    __tablename__ = 'presentations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    width = Column(Float, nullable=True, default=1000)
    height = Column(Float, nullable=True, default=562.5)
    cover_url = Column(Text, nullable=True)
    description = Column(Text)
    thumbnail_url = Column(JSONB)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=True, index=True)
    status = Column(String, nullable=False, default=PresentationStatusType.DRAFT, index=True)
    is_public = Column(Boolean, default=False, index=True)
    is_template = Column(Boolean, default=False, index=True)
    sharing_settings = Column(JSONB, default={
        'can_view': 'private',
        'can_edit': 'owner',
        'can_comment': 'collaborators',
        'allow_download': False,
        'password_protected': False,
        'password': None
    }, index=True)
    page_count = Column(Integer, default=0, index=True)
    view_count = Column(Integer, default=0, index=True)
    share_count = Column(Integer, default=0, index=True)
    clone_count = Column(Integer, default=0, index=True)
    theme_data = Column(JSONB, default={}, index=True)
    tags = Column(JSONB, index=True)
    background = Column(JSONB, nullable=True)
    ext_info = Column(JSONB, nullable=True)
    animation_settings = Column(JSONB, default={}, index=True)
    presentation_settings = Column(JSONB, default={
        'auto_advance': False,
        'advance_time': 5,
        'show_controls': True,
        'show_progress': True
    }, index=True)

    version = Column(Integer, default=1, index=True)
    parent_presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), index=True)
    last_viewed_at = Column(DateTime(timezone=True), index=True)

    # Relationships
    owner = relationship("User", back_populates="presentations", foreign_keys=[owner_id])
    template = relationship("Template", foreign_keys=[template_id])
    parent_presentation = relationship("Presentation", remote_side=[id])
    pages = relationship("PresentationPage", back_populates="presentation", cascade="all, delete-orphan")
    collaborators = relationship("PresentationCollaborator", back_populates="presentation",
                                 cascade="all, delete-orphan")
    comments = relationship("PresentationComment", back_populates="presentation", cascade="all, delete-orphan")
    shares = relationship("PresentationShare", back_populates="presentation", cascade="all, delete-orphan")


class PresentationPage(SQLBaseModel):
    __tablename__ = 'presentation_pages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    template_page_id = Column(UUID(as_uuid=True), ForeignKey('template_pages.id'), nullable=True, index=True)
    page_order = Column(Integer, nullable=False, index=True)
    page_name = Column(String, index=True)
    page_type = Column(String, nullable=True)
    page_category = Column(String, nullable=True)
    page_section = Column(String, nullable=True)
    page_data = Column(JSONB, nullable=True)
    thumbnail_url = Column(Text)
    preview_data = Column(JSONB, index=True)
    animation_count = Column(Integer, default=0, index=True)
    element_count = Column(Integer, default=0, index=True)
    text_length = Column(Integer, default=0, index=True)
    speaker_notes = Column(Text)
    tags = Column(JSONB, index=True)
    background = Column(JSONB, nullable=True)
    ext_info = Column(JSONB, nullable=True)

    # Relationships
    presentation = relationship("Presentation", back_populates="pages")
    template_page = relationship("TemplatePage", foreign_keys=[template_page_id])
    comments = relationship("PresentationComment", back_populates="page", cascade="all, delete-orphan")


class PresentationCollaborator(SQLBaseModel):
    __tablename__ = 'presentation_collaborators'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)  # Null for email invites
    email = Column(String(255), index=True)
    role = Column(SQLAEnum(CollaboratorRoleType), nullable=False, default=CollaboratorRoleType.VIEWER, index=True)

    permissions = Column(JSONB, default={
        'can_edit': False,
        'can_comment': True,
        'can_share': False,
        'can_export': False
    }, index=True)

    status = Column(String(50), default='pending', index=True)
    invite_token = Column(String(255), unique=True, index=True)
    invited_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    invited_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    accepted_at = Column(DateTime(timezone=True), index=True)
    last_accessed_at = Column(DateTime(timezone=True), index=True)

    presentation = relationship("Presentation", back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id])
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])


class PresentationComment(SQLBaseModel):
    __tablename__ = 'presentation_comments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey('presentation_pages.id'), nullable=True,
                     index=True)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    parent_comment_id = Column(UUID(as_uuid=True), ForeignKey('presentation_comments.id'), nullable=True,
                               index=True)
    content = Column(Text, nullable=False)
    status = Column(SQLAEnum(CommentStatusType), default=CommentStatusType.ACTIVE, index=True)
    position_data = Column(JSONB, index=True)
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), index=True)

    presentation = relationship("Presentation", back_populates="comments")
    page = relationship("PresentationPage", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
    parent_comment = relationship("PresentationComment", remote_side=[id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])


class PresentationShare(SQLBaseModel):
    __tablename__ = 'presentation_shares'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    shared_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    share_type = Column(String(50), nullable=False, index=True)
    share_url = Column(String(500), index=True)
    recipient_email = Column(String(255), index=True)
    expires_at = Column(DateTime(timezone=True), index=True)
    password_protected = Column(Boolean, default=False, index=True)
    view_count = Column(Integer, default=0, index=True)
    last_accessed_at = Column(DateTime(timezone=True), index=True)

    # Relationships
    presentation = relationship("Presentation", back_populates="shares")
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])


class PresentationActivity(SQLBaseModel):
    __tablename__ = 'presentation_activities'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    activity_type = Column(String(100), nullable=False, index=True)
    activity_data = Column(JSONB, default={}, index=True)
    description = Column(Text)

    ip_address = Column(String(45), index=True)
    user_agent = Column(String(500))


class PresentationVersion(SQLBaseModel):
    __tablename__ = 'presentation_versions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    presentation_id = Column(UUID(as_uuid=True), ForeignKey('presentations.id'), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    presentation_data = Column(JSONB, nullable=False,
                               index=True)
    change_summary = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
