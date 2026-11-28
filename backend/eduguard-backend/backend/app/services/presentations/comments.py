from uuid import UUID
from sqlalchemy import desc, func
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services.base import BaseService
from app.models.presentation import PresentationComment
from app.schemas.presentation import CommentCreate
from app.services.presentations.permissions import PermissionService
from app.services.presentations.activity import ActivityService


class CommentService(BaseService):
    def __init__(self, db: Session):
        super().__init__(db)
        self.permissions = PermissionService(db)
        self.activity = ActivityService(db)

    def create(self, presentation_id: UUID, data: CommentCreate, user_id: int) -> PresentationComment:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            self.permissions.can_comment(presentation, user_id),
            "Not authorized to comment"
        )

        comment = PresentationComment(
            presentation_id=presentation_id,
            user_id=user_id,
            **data.model_dump()
        )

        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        self.activity.log(presentation_id, user_id, "commented", {"comment_id": str(comment.id)})
        return comment

    def get_comments(self, presentation_id: UUID, page_id: Optional[UUID] = None,
                     user_id: Optional[int] = None) -> List[PresentationComment]:
        presentation = self._get_presentation_or_404(presentation_id)
        self._check_permission(
            self.permissions.can_access(presentation, user_id),
            "Access denied"
        )

        query = self.db.query(PresentationComment).filter(
            PresentationComment.presentation_id == presentation_id
        )

        if page_id:
            query = query.filter(PresentationComment.page_id == page_id)

        return query.order_by(PresentationComment.created_at).all()

    def resolve(self, comment_id: UUID, user_id: int) -> PresentationComment:
        comment = self._get_comment_or_404(comment_id)
        presentation = self._get_presentation_or_404(comment.presentation_id)

        self._check_permission(
            self.permissions.can_edit(presentation, user_id),
            "Not authorized to resolve comments"
        )

        comment.is_resolved = True
        comment.resolved_by_user_id = user_id
        comment.resolved_at = func.now()

        self.db.commit()
        self.db.refresh(comment)
        return comment

    def _get_comment_or_404(self, comment_id: UUID) -> PresentationComment:
        comment = self.db.query(PresentationComment).filter(PresentationComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        return comment