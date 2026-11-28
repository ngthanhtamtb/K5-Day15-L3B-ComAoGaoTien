from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, UUID4

from app.core.pptagent.types import (
    TemplateCategoryType, TemplateType, TemplateStatusType, PageType
)


class TemplateCreateRequest(BaseModel):
    name: str
    subject: str
    description: Optional[str] = None
    category: Optional[TemplateCategoryType] = None
    template_type: TemplateType = TemplateType.USER
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    difficulty_level: int = 1
    estimated_time: Optional[int] = None
    is_premium: bool = False
    price: float = 0.0


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    category: Optional[TemplateCategoryType] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    difficulty_level: Optional[int] = None
    estimated_time: Optional[int] = None
    is_premium: Optional[bool] = None
    price: Optional[float] = None
    is_public: Optional[bool] = None


class TemplatePageCreateRequest(BaseModel):
    page_data: Dict[str, Any]
    page_type: PageType
    page_order: int
    page_name: Optional[str] = None
    page_description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_data: Optional[Dict[str, Any]] = None


class TemplatePageUpdateRequest(BaseModel):
    page_data: Optional[Dict[str, Any]] = None
    page_type: Optional[PageType] = None
    page_order: Optional[int] = None
    page_name: Optional[str] = None
    page_description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_data: Optional[Dict[str, Any]] = None


class TemplateReviewRequest(BaseModel):
    rating: int
    review_text: Optional[str] = None


class TemplateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False


class TemplateReportRequest(BaseModel):
    reason: str
    description: Optional[str] = None


######## V0

class TemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=525)
    description: Optional[str] = None
    category: Optional[TemplateCategoryType] = None
    tags: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    is_premium: bool = False
    price: float = Field(0.0, ge=0)
    difficulty_level: int = Field(1, ge=1, le=5)
    estimated_time: Optional[int] = None


class TemplateCreate(TemplateBase):
    template_type: TemplateType = TemplateType.USER
    cover_url: Optional[str] = None
    file_url: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    category: Optional[TemplateCategoryType] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    is_premium: Optional[bool] = None
    price: Optional[float] = None
    difficulty_level: Optional[int] = None
    estimated_time: Optional[int] = None
    cover_url: Optional[str] = None


class TemplateResponse(TemplateBase):
    id: UUID4
    template_type: TemplateType
    status: TemplateStatusType
    is_active: bool
    is_public: bool
    is_featured: bool
    is_approved: bool
    usage_count: int
    view_count: int
    download_count: int
    like_count: int
    clone_count: int
    cover_url: Optional[str]
    file_url: Optional[str]
    slug: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]
    creator_id: Optional[int]

    class Config:
        from_attributes = True


# Template Page schemas
class TemplatePageBase(BaseModel):
    page_type: PageType
    page_order: int
    page_name: Optional[str] = None
    page_description: Optional[str] = None
    page_data: Dict[str, Any]


class TemplatePageCreate(TemplatePageBase):
    template_id: UUID4


class TemplatePageResponse(TemplatePageBase):
    id: UUID4
    template_id: UUID4
    thumbnail_url: Optional[str]
    animation_count: int
    element_count: int
    text_length: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TemplateReviewCreate(BaseModel):
    template_id: UUID4
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = None


class TemplateReviewResponse(BaseModel):
    id: UUID4
    template_id: UUID4
    user_id: int
    rating: int
    review_text: Optional[str]
    is_verified_purchase: bool
    is_helpful_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TemplateSearchParams(BaseModel):
    query: Optional[str] = None
    category: Optional[TemplateCategoryType] = None
    template_type: Optional[TemplateType] = None
    status: Optional[TemplateStatusType] = None
    tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_premium: Optional[bool] = None
    min_rating: Optional[float] = None
    difficulty_level: Optional[int] = None
    sort_by: str = "updated_at"
    sort_order: str = "desc"
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int
    page: int
    limit: int
    total_pages: int

    class Config:
        from_attributes = True
