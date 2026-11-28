from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.presentation import PresentationPage
from app.schemas.presentation import PresentationPageCreate, PresentationPageUpdate
from app.services.base import BaseService
from app.services.presentations.permissions import PermissionService


class PageService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = PermissionService(db)

    def get_pages(self, presentation_id: UUID, user_id: Optional[int] = None) -> List[PresentationPage]:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            self.permissions.can_access(presentation, user_id),
            "Access denied"
        )

        return (self.db.query(PresentationPage)
                .filter(PresentationPage.presentation_id == presentation_id)
                .order_by(PresentationPage.page_order)
                .all())

    def create(self, data: PresentationPageCreate, user_id: int) -> PresentationPage:
        presentation = self._get_presentation_or_404(data.presentation_id, user_id=user_id)
        self._check_permission(
            self.permissions.can_edit(presentation, user_id),
            "Not authorized to edit"
        )

        self.db.query(PresentationPage).filter(
            PresentationPage.presentation_id == data.presentation_id,
            PresentationPage.page_order >= data.page_order
        ).update({
            PresentationPage.page_order: PresentationPage.page_order + 1
        }, synchronize_session=False)

        create_data = {
            'presentation_id': data.presentation_id,
            'template_page_id': data.template_page_id,
            'page_order': data.page_order,
            'page_data': data.elements,
            'page_type': data.type,
            'background': data.background,
            # 'page_name': data.page_name,
            # 'speaker_notes': data.speaker_notes
        }

        page = PresentationPage(**create_data)
        self.db.add(page)

        presentation.page_count += 1

        self.db.commit()
        self.db.refresh(page)
        return page

    def update(self, page_id: UUID, data: PresentationPageUpdate, user_id: int) -> PresentationPage:
        page = self._get_page_or_404(page_id)
        presentation = self._get_presentation_or_404(page.presentation_id, user_id=user_id)

        self._check_permission(
            self.permissions.can_edit(presentation, user_id),
            "Not authorized to edit"
        )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(page, field, value)

        self.db.commit()
        self.db.refresh(page)
        return page

    def delete(self, page_id: UUID, user_id: int) -> bool:
        print(page_id)
        page = self._get_page_or_404(page_id)
        presentation = self._get_presentation_or_404(page.presentation_id, user_id=user_id)

        self._check_permission(
            self.permissions.can_edit(presentation, user_id),
            "Not authorized to edit"
        )

        deleted_page_order = page.page_order
        presentation_id = page.presentation_id

        self.db.delete(page)

        self.db.query(PresentationPage).filter(
            PresentationPage.presentation_id == presentation_id,
            PresentationPage.page_order > deleted_page_order
        ).update({
            PresentationPage.page_order: PresentationPage.page_order - 1
        }, synchronize_session=False)

        presentation.page_count = max(0, presentation.page_count - 1)

        self.db.commit()
        return True

    def _get_page_or_404(self, page_id: UUID) -> PresentationPage:
        page = self.db.query(PresentationPage).filter(PresentationPage.id == page_id).first()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return page