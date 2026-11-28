from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, or_, and_, asc, func
from fastapi import HTTPException

from app.core.pptagent.types import TemplateStatusType
from app.models.template import Template
from app.services.base import BaseService


class TemplateApprovalService(BaseService):

    def submit_for_approval(self, template_id: UUID, user_id: int) -> Template:
        template = self._get_template_or_404(template_id)

        self._check_permission(
            template.created_by_user_id == user_id,
            "Only template creator can submit for approval"
        )

        if template.status != TemplateStatusType.PRIVATE:
            raise HTTPException(
                status_code=400,
                detail="Template must be private to submit for approval"
            )

        template.status = TemplateStatusType.PENDING
        self.db.commit()
        self.db.refresh(template)

        return template

    def approve_template(self, template_id: UUID, admin_id: int, is_featured: bool = False) -> Template:
        template = self._get_template_or_404(template_id)

        if template.status != TemplateStatusType.PENDING:
            raise HTTPException(
                status_code=400,
                detail="Template must be pending approval"
            )

        template.status = TemplateStatusType.APPROVED
        template.is_approved = True
        template.approved_by_admin_id = admin_id
        template.approved_at = func.now()
        template.is_featured = is_featured

        if is_featured or template.is_public:
            template.published_at = func.now()
            template.status = TemplateStatusType.PUBLIC

        self.db.commit()
        self.db.refresh(template)

        return template

    def reject_template(self, template_id: UUID, admin_id: int, rejection_reason: str) -> Template:
        template = self._get_template_or_404(template_id)

        template.status = TemplateStatusType.REJECTED
        template.rejection_reason = rejection_reason
        template.approved_by_admin_id = admin_id

        self.db.commit()
        self.db.refresh(template)

        return template

    def get_pending_templates(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        query = self.db.query(Template).filter(
            Template.status == TemplateStatusType.PENDING,
            Template.is_active == True
        )

        total = query.count()
        templates = query.order_by(Template.created_at).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            "templates": templates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
