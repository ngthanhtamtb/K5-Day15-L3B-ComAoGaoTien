from typing import List, Optional, Dict, Any, ClassVar, Union
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, UUID4

from app.core.pptagent.types import (
    PresentationStatusType, CollaboratorRoleType, CommentStatusType, PageType
)


class ConfigData(BaseModel):
    audience: ClassVar[List[Dict[str, str]]] = [
        {"name": "Public", "value": "Public"},
        {"name": "Students", "value": "Students"},
        {"name": "Teachers", "value": "Teachers"},
        {"name": "Superiors", "value": "Superiors"},
        {"name": "Subordinates", "value": "Subordinates"},
        {"name": "Interviewer", "value": "Interviewer"},
        {"name": "Colleagues", "value": "Colleagues"}
    ]
    language: ClassVar[List[Dict[str, str]]] = [
        {"name": "English", "value": "en"},
        {"name": "Vietnamese", "value": "vi"},
        {"name": "Japanese", "value": "ja"}
    ]
    topic: ClassVar[List[Dict[str, str]]] = [
        {"name": "General Scene", "value": "General Scene"},
        {"name": "Teaching Materials", "value": "Teaching Materials"},
        {"name": "Work Summary", "value": "Work Summary"},
        {"name": "Work Plan", "value": "Work Plan"},
        {"name": "Project Report", "value": "Project Report"},
        {"name": "Solution", "value": "Solution"},
        {"name": "Research Report", "value": "Research Report"},
        {"name": "Meeting Materials", "value": "Meeting Materials"},
        {"name": "Product Introduction", "value": "Product Introduction"},
        {"name": "Company Introduction", "value": "Company Introduction"},
        {"name": "Business Plan", "value": "Business Plan"},
        {"name": "Science Popularization", "value": "Science Popularization"},
        {"name": "Public Speaking", "value": "Public Speaking"}
    ]
    tone: ClassVar[List[Dict[str, str]]] = [
        {"name": "Neutral", "value": "neutral"},
        {"name": "Formal", "value": "formal"},
        {"name": "Informal", "value": "informal"},
        {"name": "Enthusiastic", "value": "enthusiastic"},
        {"name": "Concise", "value": "concise"}
    ]
    style: ClassVar[List[Dict[str, str]]] = [
        {"name": "Modern", "value": "modern"},
        {"name": "Classic", "value": "classic"},
        {"name": "Minimalist", "value": "minimalist"},
        {"name": "Creative", "value": "creative"}
    ]
    model: ClassVar[List[Dict[str, str]]] = [
        {"name": "Gemini 2.5 Flash", "value": "gemini-2.5-flash"},
        {"name": "Gemini 2.5 Pro", "value": "gemini-2.5-pro"},
        {"name": "Gemini 2.0 Flash", "value": "gemini-2.0-flash"},
        {"name": "Gemini 2.0 Pro", "value": "gemini-2.0-pro"}
    ]
    slide_count: ClassVar[List[Dict[str, str]]] = [
        {"name": "Min Slide Count", "value": 5},
        {"name": "Max Slide Count", "value": 50}
    ]


class PresentationBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_public: bool = False
    is_template: bool = False


class PresentationCreate(PresentationBase):
    template_id: Optional[UUID4] = None
    sharing_settings: Optional[Dict[str, Any]] = None
    theme_data: Optional[Dict[str, Any]] = None
    animation_settings: Optional[Dict[str, Any]] = None
    presentation_settings: Optional[Dict[str, Any]] = None


class PresentationUpdate(BaseModel):
    title: Optional[str] = None
    # cover_url: Optional[str] = None
    description: Optional[str] = None
    # is_public: Optional[bool] = None
    # is_template: Optional[bool] = None
    # sharing_settings: Optional[Dict[str, Any]] = None
    # theme_data: Optional[Dict[str, Any]] = Field(default=None)
    slides: Optional[List[Dict[str, Any]]] = None
    # animation_settings: Optional[Dict[str, Any]] = Field(default=None)
    # presentation_settings: Optional[Dict[str, Any]] = None
    # Source dimensions for position normalization (from frontend)
    source_width: Optional[float] = Field(default=None, description="Source slide width from frontend for position normalization")
    source_height: Optional[float] = Field(default=None, description="Source slide height from frontend for position normalization")


class PresentationResponse(PresentationBase):
    id: UUID4
    owner_id: int
    template_id: Optional[UUID4]
    status: Optional[str]
    sharing_settings: Dict[str, Any]
    cover_url: Optional[str]
    thumbnail_url: Optional[str]
    page_count: int
    view_count: int
    share_count: int
    clone_count: int
    theme_data: Dict[str, Any]
    animation_settings: Dict[str, Any]
    presentation_settings: Dict[str, Any]
    version: int
    parent_presentation_id: Optional[UUID4]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]
    last_viewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PresentationPageCreateRequest(BaseModel):
    presentation_id: UUID4
    template_page_id: Optional[UUID4] = None
    page_order: int
    elements: List[Dict[str, Any]]
    background: Dict
    type: str = Field(default=PageType.CONTENT)
    page_name: Optional[str] = None
    speaker_notes: Optional[str] = None
    # Source dimensions for position normalization (from frontend)
    source_width: Optional[float] = Field(default=None, description="Source slide width from frontend for position normalization")
    source_height: Optional[float] = Field(default=None, description="Source slide height from frontend for position normalization")


class PresentationPageBase(BaseModel):
    page_order: int
    page_data: Optional[Dict[str, Any]] = None
    page_type: str = Field(default=PageType.CONTENT)
    page_name: Optional[str] = None
    speaker_notes: Optional[str] = None


class PresentationPageCreate(PresentationPageBase):
    presentation_id: UUID4
    template_page_id: Optional[UUID4] = None


class PresentationPageUpdate(BaseModel):
    page_order: Optional[int] = None
    page_name: Optional[str] = None
    page_data: Optional[Dict[str, Any]] = None
    speaker_notes: Optional[str] = None


class PresentationPageResponse(PresentationPageBase):
    id: UUID4
    presentation_id: UUID4
    template_page_id: Optional[UUID4]
    thumbnail_url: Optional[str]
    animation_count: int
    element_count: int
    text_length: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CollaboratorInvite(BaseModel):
    email: str
    role: CollaboratorRoleType = CollaboratorRoleType.VIEWER
    permissions: Optional[Dict[str, bool]] = None


class CollaboratorResponse(BaseModel):
    id: UUID4
    presentation_id: UUID4
    user_id: Optional[int]
    email: Optional[str]
    role: CollaboratorRoleType
    permissions: Dict[str, bool]
    status: str
    invited_at: datetime
    accepted_at: Optional[datetime]
    last_accessed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    content: str
    page_id: Optional[UUID4] = None
    parent_comment_id: Optional[UUID4] = None
    position_data: Optional[Dict[str, Any]] = None


class CommentResponse(BaseModel):
    id: UUID4
    presentation_id: UUID4
    page_id: Optional[UUID4]
    user_id: int
    parent_comment_id: Optional[UUID4]
    content: str
    status: CommentStatusType
    position_data: Optional[Dict[str, Any]]
    is_resolved: bool
    resolved_by_user_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ShareCreate(BaseModel):
    share_type: str  # 'link', 'email', 'social'
    recipient_email: Optional[str] = None
    expires_at: Optional[datetime] = None
    password_protected: bool = False


class ShareResponse(BaseModel):
    id: UUID4
    presentation_id: UUID4
    shared_by_user_id: int
    share_type: str
    share_url: Optional[str]
    recipient_email: Optional[str]
    expires_at: Optional[datetime]
    password_protected: bool
    view_count: int
    created_at: datetime
    last_accessed_at: Optional[datetime]

    class Config:
        from_attributes = True
