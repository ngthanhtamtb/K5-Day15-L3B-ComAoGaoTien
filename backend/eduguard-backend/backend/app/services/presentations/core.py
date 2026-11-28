import traceback
from uuid import UUID
from sqlalchemy import desc, func
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.schemas.presentation import PresentationCreate, PresentationUpdate
from app.services.presentations.permissions import PermissionService
from app.services.presentations.activity import ActivityService
from app.models.presentation import Presentation, PresentationPage
from app.services.base import BaseService
from app.utils.pptx_utils import normalize_slides_data


class PresentationCoreService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = PermissionService(db)
        self.activity = ActivityService(db)

    def create(self, data: PresentationCreate, user_id: int) -> Presentation:
        presentation = Presentation(**data.model_dump(), owner_id=user_id)
        self.db.add(presentation)
        self.db.commit()
        self.db.refresh(presentation)

        self.activity.log(presentation.id, user_id, "created", {"title": presentation.title})
        return presentation

    def get(self, presentation_id: UUID, user_id: Optional[int] = None) -> Presentation:
        presentation = self._get_presentation_or_404(presentation_id, user_id)
        self._check_permission(
            self.permissions.can_access(presentation, user_id),
            "Access denied"
        )
        return presentation

    def update(self, presentation_id: UUID, data: PresentationUpdate, user_id: int) -> Presentation:
        presentation = self.get(presentation_id, user_id)
        self._check_permission(
            self.permissions.can_edit(presentation, user_id),
            "Not authorized to edit"
        )

        pages_data = data.slides

        if pages_data is not None:
            # Normalize element positions if source dimensions are provided
            source_width = data.source_width
            source_height = data.source_height
            if source_width and source_height:
                pages_data = normalize_slides_data(pages_data, source_width, source_height)

            self._update_presentation_pages(presentation_id, pages_data)

        if pages_data is not None:
            page_count = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).count()
            presentation.page_count = page_count

        update_data = data.model_dump(exclude={'pages', 'slides', 'source_width', 'source_height'}, exclude_unset=True)
        for field, value in update_data.items():
            setattr(presentation, field, value)

        self.db.commit()
        self.db.refresh(presentation)

        self.activity.log(presentation_id, user_id, "edited", update_data)
        return presentation

    def delete(self, presentation_id: UUID, user_id: int) -> bool:
        presentation = self.get(presentation_id, user_id)
        self._check_permission(
            presentation.owner_id == user_id,
            "Only owner can delete"
        )

        self.db.delete(presentation)
        self.db.commit()

        self.activity.log(presentation_id, user_id, "deleted", {})
        return True

    def list_user_presentations(self, user_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        try:
            query = self.db.query(Presentation).filter(Presentation.owner_id == user_id)
            total = query.count()

            presentations = (query.order_by(desc(Presentation.updated_at))
                             .offset((page - 1) * limit)
                             .limit(limit)
                             .all())

            return {
                "presentations": presentations,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit
            }
        except Exception as exc:
            print(f"list user presentations error: {traceback.format_exc()}")

    def clone(self, presentation_id: UUID, user_id: int, new_title: Optional[str] = None) -> Presentation:
        original = self.get(presentation_id, user_id)

        cloned = Presentation(
            title=new_title or f"Copy of {original.title}",
            description=original.description,
            owner_id=user_id,
            template_id=original.template_id,
            theme_data=original.theme_data,
            animation_settings=original.animation_settings,
            presentation_settings=original.presentation_settings,
            parent_presentation_id=original.id
        )

        self.db.add(cloned)
        self.db.flush()

        self._clone_pages(original.id, cloned.id)

        original.clone_count += 1
        cloned.page_count = original.page_count

        self.db.commit()
        self.db.refresh(cloned)

        self.activity.log(cloned.id, user_id, "cloned", {"original_id": str(presentation_id)})
        return cloned

    def _update_presentation_pages(self, presentation_id: UUID, pages_data: List[Dict[str, Any]]):
        incoming_page_ids = [page_data.get('id') for page_data in pages_data if page_data.get('id')]

        if incoming_page_ids:
            self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id,
                ~PresentationPage.id.in_(incoming_page_ids)
            ).delete(synchronize_session=False)
        else:
            self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation_id
            ).delete(synchronize_session=False)

        for page_data in pages_data:
            page_id = page_data.get('id')

            if page_id:
                existing_page = self.db.query(PresentationPage).filter(
                    PresentationPage.id == page_id,
                    PresentationPage.presentation_id == presentation_id
                ).first()

                if existing_page:
                    for field, value in page_data.items():
                        if field == 'elements':
                            existing_page.page_data = value
                        if hasattr(existing_page, field) and field != 'id':
                            setattr(existing_page, field, value)

                    self.db.commit()
                else:
                    self._create_new_page(presentation_id, page_data)
            else:
                self._create_new_page(presentation_id, page_data)

    # def _update_presentation_pages(self, presentation_id: UUID, pages_data: List[Dict[str, Any]]):
    #     for page_data in pages_data:
    #         page_id = page_data.get('id')
    #
    #         if page_id:
    #             existing_page = self.db.query(PresentationPage).filter(
    #                 PresentationPage.id == page_id,
    #                 PresentationPage.presentation_id == presentation_id
    #             ).first()
    #
    #             if existing_page:
    #                 for field, value in page_data.items():
    #                     if hasattr(existing_page, field) and field != 'id':
    #                         setattr(existing_page, field, value)
    #             else:
    #                 self._create_new_page(presentation_id, page_data)
    #         else:
    #             # No page ID provided - create new page
    #             self._create_new_page(presentation_id, page_data)

    def _create_new_page(self, presentation_id: UUID, page_data: Dict[str, Any]):
        page_data_copy = page_data.copy()
        page_data_copy.pop('id', None)

        if 'elements' in page_data_copy:
            elements = page_data_copy.pop('elements')
            page_data_copy['page_data'] = elements

        new_page = PresentationPage(
            presentation_id=presentation_id,
            **page_data_copy
        )

        self.db.add(new_page)

    def _clone_pages(self, source_id: UUID, target_id: UUID):
        pages = self.db.query(PresentationPage).filter(
            PresentationPage.presentation_id == source_id
        ).order_by(PresentationPage.page_order).all()

        for page in pages:
            cloned_page = PresentationPage(
                presentation_id=target_id,
                template_page_id=page.template_page_id,
                page_order=page.page_order,
                page_name=page.page_name,
                page_type=page.page_type,
                page_data=page.page_data,
                speaker_notes=page.speaker_notes
            )
            self.db.add(cloned_page)