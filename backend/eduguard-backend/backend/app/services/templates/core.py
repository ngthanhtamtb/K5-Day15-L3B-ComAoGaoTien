from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, or_, asc
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException

from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateSearchParams
from app.core.pptagent.types import PageType, TemplateType, TemplateStatusType
from app.models.template import Template, TemplatePage
from app.services.base import BaseService
from app.services.templates.permissions import TemplatePermissionService
from app.services.templates.analytics import TemplateAnalyticsService


class TemplateCoreService(BaseService):

    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = TemplatePermissionService(db)
        self.analytics = TemplateAnalyticsService(db)

    def create(self, template_data: dict, user_id: int, slides_data: List[dict]) -> Template:
        try:
            slug = self._generate_slug(template_data["name"])

            template = Template(
                **template_data,
                slug=slug,
                created_by_user_id=user_id,
                # template_type=template_data.get("template_type", "user"),
                status="private",
                is_active=True
            )

            self.db.add(template)
            self.db.flush()

            self._create_pages(template.id, slides_data)

            self.db.commit()
            self.db.refresh(template)

            return template

        except Exception as e:
            self.db.rollback()
            raise e

    def get(self, template_id: UUID, user_id: Optional[int] = None) -> Template:
        template = self.db.query(Template).options(
            selectinload(Template.pages)
        ).filter(
            Template.id == template_id,
            Template.is_active == True
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        self._check_permission(
            self.permissions.can_view(template, user_id),
            "No permission to view this template"
        )

        if user_id:
            self.analytics.log_usage(template_id, user_id, "view")

        return template

    def update(self, template_id: UUID, update_data: dict, user_id: int) -> Template:
        template = self._get_template_or_404(template_id)
        self._check_permission(
            self.permissions.can_edit(template, user_id),
            "No permission to edit this template"
        )

        for field, value in update_data.items():
            if hasattr(template, field):
                setattr(template, field, value)

        self.db.commit()
        self.db.refresh(template)

        return template

    def delete(self, template_id: UUID, user_id: int) -> bool:
        template = self._get_template_or_404(template_id)
        self._check_permission(
            self.permissions.can_delete(template, user_id),
            "No permission to delete this template"
        )

        template.is_active = False
        self.db.commit()

        return True

    def search(self, params: TemplateSearchParams, user_id: Optional[int] = None) -> Dict[str, Any]:
        query = self.db.query(Template).filter(Template.is_active == True)

        if params.query:
            query = query.filter(
                or_(
                    Template.name.ilike(f"%{params.query}%"),
                    Template.subject.ilike(f"%{params.query}%"),
                    Template.description.ilike(f"%{params.query}%"),
                    Template.keywords.op("@>")(f'["{params.query}"]')
                )
            )

        if params.category:
            query = query.filter(Template.category == params.category)
        if params.template_type:
            query = query.filter(Template.template_type == params.template_type)
        if params.tags:
            for tag in params.tags:
                query = query.filter(Template.tags.op("@>")(f'["{tag}"]'))
        if params.is_premium is not None:
            query = query.filter(Template.is_premium == params.is_premium)
        if params.difficulty_level:
            query = query.filter(Template.difficulty_level == params.difficulty_level)

        if not user_id:
            query = query.filter(Template.status == TemplateStatusType.PUBLIC)
        else:
            query = query.filter(
                or_(
                    Template.status == TemplateStatusType.PUBLIC,
                    Template.created_by_user_id == user_id
                )
            )

        sort_column = getattr(Template, params.sort_by, Template.updated_at)
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        total = query.count()
        templates = query.offset((params.page - 1) * params.page_size).limit(params.page_size).all()

        results = []
        for t in templates:
            like_and_fav = t.is_like_and_is_favorite(db=self.db, user_id=user_id)
            results.append({
                **t.__dict__,
                "is_favorite": like_and_fav["is_favorite"],
                "is_like": like_and_fav["is_like"]
            })

        return {
            "templates": results,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "total_pages": (total + params.page_size - 1) // params.page_size
        }

    def get_user_templates(self, user_id: int, status: Optional[TemplateStatusType] = None,
                           page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        query = self.db.query(Template).filter(
            Template.created_by_user_id == user_id,
            Template.is_active == True
        )

        if status:
            query = query.filter(Template.status == status)

        total = query.count()
        templates = query.order_by(desc(Template.updated_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            "templates": templates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def clone(self, template_id: UUID, user_id: int, new_name: Optional[str] = None) -> Template:
        original = self.get(template_id, user_id)
        self.analytics.log_usage(template_id, user_id, "clone")

        cloned = Template(
            name=new_name or f"Copy of {original.name}",
            subject=original.subject,
            description=original.description,
            created_by_user_id=user_id,
            template_type=TemplateType.USER,
            category=original.category,
            tags=original.tags,
            difficulty_level=original.difficulty_level,
            estimated_time=original.estimated_time,
            slug=self._generate_slug(new_name or f"Copy of {original.name}")
        )

        self.db.add(cloned)
        self.db.flush()

        self._clone_pages(original.id, cloned.id)

        original.clone_count += 1

        self.db.commit()
        self.db.refresh(cloned)

        return cloned

    def _create_pages(self, template_id: UUID, slides_data: List[dict]):
        for index, slide in enumerate(slides_data):
            page_type = self._determine_page_type(slide.get("type"))
            elements = slide.get("elements", [])

            page = TemplatePage(
                template_id=template_id,
                page_type=page_type,
                page_order=index + 1,
                page_name=f"Slide {index + 1}",
                page_description=f"Page {index + 1} - {slide.get('type', 'content')} type",
                page_data=slide,
                animation_count=self._count_animations(elements),
                element_count=len(elements),
                text_filled_count=self._count_text_elements(elements),
                preview_data={
                    "background": slide.get("background", {}),
                    "elements_preview": [elem.get("type") for elem in elements[:3]]
                }
            )

            self.db.add(page)

    def _clone_pages(self, source_id: UUID, target_id: UUID):
        pages = self.db.query(TemplatePage).filter(
            TemplatePage.template_id == source_id
        ).order_by(TemplatePage.page_order).all()

        for page in pages:
            cloned_page = TemplatePage(
                template_id=target_id,
                page_type=page.page_type,
                page_order=page.page_order,
                page_name=page.page_name,
                page_description=page.page_description,
                page_data=page.page_data,
                thumbnail_url=page.thumbnail_url,
                preview_data=page.preview_data,
                animation_count=page.animation_count,
                element_count=page.element_count,
                text_filled_count=page.text_filled_count
            )
            self.db.add(cloned_page)

    def _determine_page_type(self, slide_type: str):
        type_mapping = {
            "cover": PageType.COVER,
            "contents": PageType.CONTENTS,
            "content": PageType.CONTENT,
            "transition": PageType.TRANSITION,
            "end": PageType.END
        }
        return type_mapping.get(slide_type, PageType.CONTENT)

    def _count_text_elements(self, elements: List[dict]) -> int:
        count = 0
        for element in elements:
            if element.get("type") == "text" and element.get("content"):
                content = element.get("content", "")
                if (isinstance(content, str) and content.strip()) or isinstance(content, dict):
                    count += 1
        return count

    def _count_animations(self, elements: List[dict]) -> int:
        count = 0
        for element in elements:
            if any(element.get(key) for key in ["animation", "animate", "transition", "effect"]):
                count += 1
        return count
