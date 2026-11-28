from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import desc, or_, asc
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status as http_status

from app.models.template import TemplatePage
from app.schemas.template import TemplatePageCreate
from app.core.pptagent.types import PageScopeType, PageCategoryType, PageSectionType
from app.services.base import BaseService
from app.services.templates.permissions import TemplatePermissionService


class TemplatePageService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = TemplatePermissionService(db)

    def get_template_pages(self, template_id: UUID) -> List[TemplatePage]:

        return self.db.query(TemplatePage).filter(
            TemplatePage.template_id == template_id
        ).order_by(TemplatePage.page_order).all()

    def create_page(self, page_data: TemplatePageCreate) -> TemplatePage:

        page = TemplatePage(**page_data.dict())
        self.db.add(page)
        self.db.commit()
        self.db.refresh(page)
        return page

    def create_standalone_page(self, page_data: dict, user_id: int) -> TemplatePage:

        page = TemplatePage(template_id=None, **page_data)
        self.db.add(page)
        self.db.commit()
        self.db.refresh(page)
        return page

    def get_standalone_pages(
            self,
            page_scope: Optional[PageScopeType] = None,
            page_category: Optional[PageCategoryType] = None,
            page_section: Optional[PageSectionType] = None,
            active_only: bool = True,
            tags: Optional[List[str]] = None,
            page: int = 1,
            limit: int = 50,
            order_by: str = "desc",
            user_id: Optional[int] = None
    ):

        query = self.db.query(TemplatePage).filter(TemplatePage.template_id.is_(None))

        if page_scope:
            query = query.filter(TemplatePage.page_scope == page_scope)

        if page_category:
            query = query.filter(TemplatePage.page_category == page_category)

        if page_section:
            query = query.filter(TemplatePage.page_section == page_section)

        # if active_only:
        #     query = query.filter(TemplatePage.is_active == True)

        if tags:
            query = query.filter(TemplatePage.tags.op('@>')([tags]))

        total = query.count()

        order = asc(TemplatePage.created_at) if order_by.lower() == "asc" else desc(TemplatePage.created_at)

        pages = (
            query.order_by(order)
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "pages": pages,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }

    def get_standalone_page(self, page_id: UUID, user_id: Optional[int] = None) -> TemplatePage:

        page = self.db.query(TemplatePage).filter(
            TemplatePage.id == page_id,
            TemplatePage.template_id.is_(None)
        ).first()

        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        if page.page_scope == PageScopeType.USER and page.created_by != user_id:
            raise HTTPException(status_code=403, detail="No permission to access this page")

        page = self._page_to_detailed(page)

        return page

    def update_standalone_page(
            self,
            page_id: UUID,
            user_id: int,
            **update_data
    ) -> TemplatePage:
        page = self.db.query(TemplatePage).filter(
            TemplatePage.id == page_id
        ).first()

        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        self._check_permission(
            self.permissions.can_edit(page, user_id),
            "No permission to delete this page"
        )

        for field, value in update_data.items():
            if hasattr(page, field):
                setattr(page, field, value)

        self.db.commit()
        self.db.refresh(page)

        return page

    def delete_standalone_page(self, page_id: UUID, user_id: int) -> bool:
        page = self.db.query(TemplatePage).filter(
            TemplatePage.id == page_id
        ).first()

        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        self._check_permission(
            self.permissions.can_delete(page, user_id),
            "No permission to delete this page"
        )

        self.db.delete(page)
        self.db.commit()

        return True

    def increment_usage(self, page_id: UUID):

        self.db.query(TemplatePage).filter(TemplatePage.id == page_id).update({
            TemplatePage.usage_count: TemplatePage.usage_count + 1,
            TemplatePage.last_used_at: datetime.now()
        })
        self.db.commit()

    def _page_to_detailed(self, page: TemplatePage) -> dict:
        return {
            "id": str(page.id),
            "page_name": page.page_name,
            "page_description": page.page_description,
            "page_type": page.page_type if page.page_type else None,
            "page_category": page.page_category if page.page_category else None,
            "page_section": page.page_section if page.page_section else None,
            "page_scope": page.page_scope,
            "thumbnail_url": page.thumbnail_url,
            "page_data": page.page_data,
            "preview_data": page.preview_data,
            "tags": page.tags,
            "animation_count": page.animation_count,
            "element_count": page.element_count,
            "text_filled_count": page.text_filled_count,
            "is_active": page.is_active,
            "usage_count": page.usage_count,
            "last_used_at": page.last_used_at.isoformat() if page.last_used_at else None,
            "created_at": page.created_at.isoformat() if page.created_at else None,
            "updated_at": page.updated_at.isoformat() if page.updated_at else None
        }
