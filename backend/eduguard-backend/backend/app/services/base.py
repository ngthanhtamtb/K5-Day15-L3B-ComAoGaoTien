import re
import secrets
import string
import traceback
from abc import ABC
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.template import Template
from app.models.presentation import Presentation


class BaseService(ABC):

    def __init__(self, db: Session):
        self.db = db

    def _get_presentation_or_404(self, presentation_id: UUID, user_id: Optional[int] = None) -> Presentation:
        try:
            presentation = self.db.query(Presentation).filter(Presentation.id == presentation_id,
                                                              Presentation.owner_id == user_id).first()
            if not presentation:
                raise HTTPException(status_code=404, detail="Presentation not found")

            return presentation
        except Exception as exc:
            print(f"presentation_or_404 error: {traceback.format_exc()}")

    def _get_template_or_404(self, template_id: UUID) -> Template:
        template = self.db.query(Template).filter(
            Template.id == template_id,
            Template.is_active == True
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    def _check_permission(self, condition: bool, message: str = "Permission denied"):
        if not condition:
            raise HTTPException(status_code=403, detail=message)

    def _generate_slug(self, name: str) -> str:
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)

        counter = 1
        original_slug = slug
        while self.db.query(Template).filter(Template.slug == slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1

        return slug

    def _generate_token(self, length: int = 16) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))