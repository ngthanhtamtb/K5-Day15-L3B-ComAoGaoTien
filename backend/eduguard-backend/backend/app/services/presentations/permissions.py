from typing import Optional
from uuid import UUID

from app.models.presentation import Presentation, PresentationCollaborator
from app.services.base import BaseService


class PermissionService(BaseService):

    def can_access(self, presentation: Presentation, user_id: Optional[int]) -> bool:
        if presentation.is_public:
            return True

        if not user_id or presentation.owner_id == user_id:
            return bool(user_id)

        return self._is_collaborator(presentation.id, user_id)

    def can_edit(self, presentation, user_id: int) -> bool:
        if not presentation:
            return False

        if presentation.owner_id == user_id:
            return True

        collaborator = self._get_collaborator(presentation.id, user_id)
        return collaborator and collaborator.permissions.get("can_edit", False)

    def can_comment(self, presentation: Presentation, user_id: int) -> bool:
        comment_setting = presentation.sharing_settings.get("can_comment", "disabled")

        if comment_setting == "disabled":
            return False
        elif comment_setting == "anyone":
            return True
        elif comment_setting == "collaborators":
            return self.can_access(presentation, user_id)

        return False

    def can_share(self, presentation: Presentation, user_id: int) -> bool:
        if presentation.owner_id == user_id:
            return True

        collaborator = self._get_collaborator(presentation.id, user_id)
        return collaborator and collaborator.permissions.get("can_share", False)

    def _is_collaborator(self, presentation_id: UUID, user_id: int) -> bool:
        return self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.presentation_id == presentation_id,
            PresentationCollaborator.user_id == user_id,
            PresentationCollaborator.status == "accepted"
        ).first() is not None

    def _get_collaborator(self, presentation_id: UUID, user_id: int) -> Optional[PresentationCollaborator]:
        return self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.presentation_id == presentation_id,
            PresentationCollaborator.user_id == user_id,
            PresentationCollaborator.status == "accepted"
        ).first()