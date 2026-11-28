from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, or_, and_, asc, func
from fastapi import HTTPException

from app.models.template import Template, TemplateLike, UserFavoriteTemplate, TemplateReview
from app.services.base import BaseService


class TemplateInteractionService(BaseService):

    def like_template(self, template_id: UUID, user_id: int) -> bool:
        existing_like = self.db.query(TemplateLike).filter(
            and_(TemplateLike.template_id == template_id, TemplateLike.user_id == user_id)
        ).first()

        template = self._get_template_or_404(template_id)

        if existing_like:
            self.db.delete(existing_like)
            template.like_count = max(0, template.like_count - 1)
            self.db.commit()
            return False
        else:
            like = TemplateLike(template_id=template_id, user_id=user_id)
            self.db.add(like)
            template.like_count += 1
            self.db.commit()
            return True

    def add_to_favorites(self, template_id: UUID, user_id: int) -> bool:
        existing = self.db.query(UserFavoriteTemplate).filter(
            and_(UserFavoriteTemplate.template_id == template_id, UserFavoriteTemplate.user_id == user_id)
        ).first()

        if existing:
            self.db.delete(existing)
            self.db.commit()
            return False
        else:
            favorite = UserFavoriteTemplate(template_id=template_id, user_id=user_id)
            self.db.add(favorite)
            self.db.commit()
            return True

    def get_user_favorites(self, user_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        query = self.db.query(Template).join(UserFavoriteTemplate).filter(
            UserFavoriteTemplate.user_id == user_id,
            Template.is_active == True
        )

        total = query.count()
        templates = query.order_by(desc(UserFavoriteTemplate.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            "templates": templates,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def create_review(self, template_id: UUID, user_id: int, rating: int,
                      review_text: Optional[str] = None) -> TemplateReview:
        if not 1 <= rating <= 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

        existing = self.db.query(TemplateReview).filter(
            and_(TemplateReview.template_id == template_id, TemplateReview.user_id == user_id)
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="You have already reviewed this template")

        review = TemplateReview(
            template_id=template_id,
            user_id=user_id,
            rating=rating,
            review_text=review_text
        )

        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)

        return review

    def get_template_reviews(self, template_id: UUID, page: int = 1,
                             page_size: int = 20) -> Dict[str, Any]:
        query = self.db.query(TemplateReview).filter(TemplateReview.template_id == template_id)

        total = query.count()
        reviews = query.order_by(desc(TemplateReview.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        avg_rating = self.db.query(func.avg(TemplateReview.rating)).filter(
            TemplateReview.template_id == template_id
        ).scalar() or 0

        return {
            "reviews": reviews,
            "total": total,
            "average_rating": round(avg_rating, 1),
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }