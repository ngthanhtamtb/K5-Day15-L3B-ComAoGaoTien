import secrets
import string
from uuid import UUID
from typing import Optional, Dict, Any, List
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.presentation import PresentationCollaborator
from app.schemas.presentation import CollaboratorInvite
from app.services.base import BaseService
from app.services.presentations.permissions import PermissionService


class CollaborationService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = PermissionService(db)

    def invite(self, presentation_id: UUID, data: CollaboratorInvite, user_id: int) -> PresentationCollaborator:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            presentation.owner_id == user_id,
            "Only owner can invite collaborators"
        )

        existing = self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.presentation_id == presentation_id,
            PresentationCollaborator.email == data.email
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="User already invited")

        collaborator = PresentationCollaborator(
            presentation_id=presentation_id,
            email=data.email,
            role=data.role,
            permissions=data.permissions or self._get_default_permissions(data.role),
            invite_token=self._generate_token(),
            invited_by_user_id=user_id
        )

        self.db.add(collaborator)
        self.db.commit()
        self.db.refresh(collaborator)

        # TODO: Send email invitation
        return collaborator

    def accept_invitation(self, invite_token: str, user_id: int) -> PresentationCollaborator:
        collaborator = self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.invite_token == invite_token,
            PresentationCollaborator.status == "pending"
        ).first()

        if not collaborator:
            raise HTTPException(status_code=404, detail="Invalid invitation")

        collaborator.user_id = user_id
        collaborator.status = "accepted"
        collaborator.accepted_at = func.now()

        self.db.commit()
        self.db.refresh(collaborator)
        return collaborator

    def remove_collaborator(self, presentation_id: UUID, collaborator_id: UUID, user_id: int) -> bool:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            presentation.owner_id == user_id,
            "Only owner can remove collaborators"
        )

        collaborator = self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.id == collaborator_id,
            PresentationCollaborator.presentation_id == presentation_id
        ).first()

        if not collaborator:
            raise HTTPException(status_code=404, detail="Collaborator not found")

        self.db.delete(collaborator)
        self.db.commit()
        return True

    def list_collaborators(self, presentation_id: UUID, user_id: int) -> List[PresentationCollaborator]:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            self.permissions.can_access(presentation, user_id),
            "Access denied"
        )

        return self.db.query(PresentationCollaborator).filter(
            PresentationCollaborator.presentation_id == presentation_id
        ).all()

    def _generate_token(self, length: int = 32) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _get_default_permissions(self, role: str) -> Dict[str, bool]:
        """Get default permissions for role"""
        permissions_map = {
            "owner": {"can_edit": True, "can_comment": True, "can_share": True, "can_export": True},
            "editor": {"can_edit": True, "can_comment": True, "can_share": False, "can_export": True},
            "commenter": {"can_edit": False, "can_comment": True, "can_share": False, "can_export": False},
            "viewer": {"can_edit": False, "can_comment": False, "can_share": False, "can_export": False}
        }
        return permissions_map.get(role, permissions_map["viewer"])