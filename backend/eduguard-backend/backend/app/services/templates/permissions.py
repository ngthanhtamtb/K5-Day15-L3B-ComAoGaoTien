from typing import Optional

from app.services.base import BaseService
from app.core.pptagent.types import TemplateStatusType
from app.models.template import Template


class TemplatePermissionService(BaseService):

    def can_view(self, template: Template, user_id: Optional[int]) -> bool:
        if template.status == TemplateStatusType.PUBLIC:
            return True

        if user_id and template.created_by_user_id == user_id:
            return True

        return False

    def can_edit(self, template: Template, user_id: int) -> bool:
        return template.created_by_user_id == user_id

    def can_delete(self, template: Template, user_id: int) -> bool:
        return template.created_by_user_id == user_id

    def can_approve(self, user_role: str) -> bool:
        return user_role in ['admin', 'moderator']
