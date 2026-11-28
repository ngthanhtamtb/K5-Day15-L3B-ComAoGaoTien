from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import desc, or_, asc
from fastapi import HTTPException

from app.services.base import BaseService
from app.models.template import TemplateReport


class TemplateReportService(BaseService):

    def report_template(self, template_id: UUID, user_id: int, reason: str,
                        description: Optional[str] = None) -> TemplateReport:
        existing = self.db.query(TemplateReport).filter(
            TemplateReport.template_id == template_id,
            TemplateReport.reported_by_user_id == user_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Template already reported by this user"
            )

        report = TemplateReport(
            template_id=template_id,
            reported_by_user_id=user_id,
            reason=reason,
            description=description
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def get_reports(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        query = self.db.query(TemplateReport)

        total = query.count()
        reports = query.order_by(desc(TemplateReport.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            "reports": reports,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
