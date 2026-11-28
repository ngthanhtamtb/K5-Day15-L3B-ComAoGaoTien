from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy import func

from app.services.base import BaseService
from app.models.template import TemplateUsage


class TemplateAnalyticsService(BaseService):

    def log_usage(self, template_id: UUID, user_id: Optional[int], action_type: str,
                  context_data: Optional[Dict[str, Any]] = None):
        usage = TemplateUsage(
            template_id=template_id,
            user_id=user_id,
            action_type=action_type,
            context_data=context_data or {}
        )
        self.db.add(usage)

        template = self._get_template_or_404(template_id)
        if action_type == "view":
            template.view_count += 1
        elif action_type == "download":
            template.download_count += 1
        elif action_type == "clone":
            template.clone_count += 1

        self.db.commit()

    def get_analytics(self, template_id: UUID, user_id: int, days: int = 30) -> Dict[str, Any]:
        template = self._get_template_or_404(template_id)
        self._check_permission(
            template.created_by_user_id == user_id,
            "Only template creator can view analytics"
        )

        date_threshold = datetime.now() - timedelta(days=days)

        usage_stats = self.db.query(
            TemplateUsage.action_type,
            func.count(TemplateUsage.id).label('count')
        ).filter(
            TemplateUsage.template_id == template_id,
            TemplateUsage.used_at >= date_threshold
        ).group_by(TemplateUsage.action_type).all()

        daily_usage = self.db.query(
            func.date(TemplateUsage.used_at).label('date'),
            func.count(TemplateUsage.id).label('count')
        ).filter(
            TemplateUsage.template_id == template_id,
            TemplateUsage.used_at >= date_threshold
        ).group_by(func.date(TemplateUsage.used_at)).all()

        return {
            "template": template,
            "usage_stats": [{"action": stat.action_type, "count": stat.count} for stat in usage_stats],
            "daily_usage": [{"date": str(usage.date), "count": usage.count} for usage in daily_usage],
            "total_views": template.view_count,
            "total_downloads": template.download_count,
            "total_likes": template.like_count,
            "total_clones": template.clone_count
        }
