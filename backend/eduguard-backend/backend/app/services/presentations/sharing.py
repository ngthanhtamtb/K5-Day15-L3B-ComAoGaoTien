import secrets
import string
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.base import BaseService
from app.models.presentation import PresentationShare, Presentation
from app.schemas.presentation import ShareCreate
from app.services.presentations.permissions import PermissionService
from app.services.presentations.activity import ActivityService


class SharingService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = PermissionService(db)
        self.activity = ActivityService(db)

    def create_share(self, presentation_id: UUID, data: ShareCreate, user_id: int) -> PresentationShare:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            self.permissions.can_share(presentation, user_id),
            "Not authorized to share"
        )

        share_url = f"/shared/{presentation_id}/{self._generate_token(16)}"

        share = PresentationShare(
            presentation_id=presentation_id,
            shared_by_user_id=user_id,
            share_url=share_url,
            **data.model_dump()
        )

        self.db.add(share)
        presentation.share_count += 1

        self.db.commit()
        self.db.refresh(share)

        self.activity.log(presentation_id, user_id, "shared", {"share_type": data.share_type})
        return share

    def access_shared(self, share_url: str, password: Optional[str] = None) -> Presentation:
        share = self.db.query(PresentationShare).filter(
            PresentationShare.share_url == share_url
        ).first()

        if not share:
            raise HTTPException(status_code=404, detail="Invalid share link")

        if share.expires_at and share.expires_at < func.now():
            raise HTTPException(status_code=410, detail="Share link expired")

        if share.password_protected and not password:
            raise HTTPException(status_code=401, detail="Password required")

        share.view_count += 1
        share.last_accessed_at = func.now()
        share.presentation.view_count += 1

        self.db.commit()
        return share.presentation

    def _generate_token(self, length: int = 16) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))