from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session

from app.services.templates.core import TemplateCoreService
from app.services.templates.pages import TemplatePageService
from app.services.templates.interactions import TemplateInteractionService
from app.services.templates.approval import TemplateApprovalService
from app.services.templates.collections import TemplateCollectionService
from app.services.templates.reports import TemplateReportService
from app.services.templates.analytics import TemplateAnalyticsService


class TemplateService:

    def __init__(self, db: Session):
        self.db = db
        self.core = TemplateCoreService(db)
        self.pages = TemplatePageService(db)
        self.interactions = TemplateInteractionService(db)
        self.approval = TemplateApprovalService(db)
        self.collections = TemplateCollectionService(db)
        self.reports = TemplateReportService(db)
        self.analytics = TemplateAnalyticsService(db)

    def create_template_with_pages(self, *args, **kwargs):
        return self.core.create(*args, **kwargs)

    def get_template(self, *args, **kwargs):
        return self.core.get(*args, **kwargs)

    def update_template(self, *args, **kwargs):
        return self.core.update(*args, **kwargs)

    def delete_template(self, *args, **kwargs):
        return self.core.delete(*args, **kwargs)

    def search_templates(self, *args, **kwargs):
        return self.core.search(*args, **kwargs)

    def get_templates(self, *args, **kwargs):
        return self.core.search(*args, **kwargs)

    def get_my_templates(self, *args, **kwargs):
        return self.core.get_user_templates(*args, **kwargs)

    def get_user_templates(self, *args, **kwargs):
        return self.core.get_user_templates(*args, **kwargs)

    def clone_template(self, *args, **kwargs):
        return self.core.clone(*args, **kwargs)

    def download_template(self, template_id: UUID, user_id: int):
        template = self.core.get(template_id, user_id)
        self.analytics.log_usage(template_id, user_id, "download")
        template.download_count += 1
        self.db.commit()
        return template

    def get_template_pages(self, *args, **kwargs):
        return self.pages.get_template_pages(*args, **kwargs)

    def create_template_page(self, *args, **kwargs):
        return self.pages.create_page(*args, **kwargs)

    def create_standalone_page(self, *args, **kwargs):
        return self.pages.create_standalone_page(*args, **kwargs)

    def get_standalone_pages(self, *args, **kwargs):
        return self.pages.get_standalone_pages(*args, **kwargs)

    def get_standalone_page(self, *args, **kwargs):
        return self.pages.get_standalone_page(*args, **kwargs)

    def update_standalone_page(self, *args, **kwargs):
        return self.pages.update_standalone_page(*args, **kwargs)

    def delete_standalone_page(self, *args, **kwargs):
        return self.pages.delete_standalone_page(*args, **kwargs)

    def increment_page_usage(self, *args, **kwargs):
        return self.pages.increment_usage(*args, **kwargs)

    def like_template(self, *args, **kwargs):
        return self.interactions.like_template(*args, **kwargs)

    def add_to_favorites(self, *args, **kwargs):
        return self.interactions.add_to_favorites(*args, **kwargs)

    def get_user_favorites(self, *args, **kwargs):
        return self.interactions.get_user_favorites(*args, **kwargs)

    def create_review(self, template_id: UUID, user_id: int, rating: int, review_text: Optional[str] = None):
        return self.interactions.create_review(template_id, user_id, rating, review_text)

    def get_template_reviews(self, *args, **kwargs):
        return self.interactions.get_template_reviews(*args, **kwargs)

    def submit_for_approval(self, *args, **kwargs):
        return self.approval.submit_for_approval(*args, **kwargs)

    def approve_template(self, *args, **kwargs):
        return self.approval.approve_template(*args, **kwargs)

    def reject_template(self, *args, **kwargs):
        return self.approval.reject_template(*args, **kwargs)

    def get_pending_templates(self, *args, **kwargs):
        return self.approval.get_pending_templates(*args, **kwargs)

    def create_collection(self, *args, **kwargs):
        return self.collections.create_collection(*args, **kwargs)

    def add_template_to_collection(self, *args, **kwargs):
        return self.collections.add_to_collection(*args, **kwargs)

    def get_user_collections(self, *args, **kwargs):
        return self.collections.get_user_collections(*args, **kwargs)

    def report_template(self, *args, **kwargs):
        return self.reports.report_template(*args, **kwargs)

    def get_template_analytics(self, *args, **kwargs):
        return self.analytics.get_analytics(*args, **kwargs)

    def log_template_usage(self, *args, **kwargs):
        return self.analytics.log_usage(*args, **kwargs)

    def _log_template_usage(self, *args, **kwargs):
        return self.analytics.log_usage(*args, **kwargs)
