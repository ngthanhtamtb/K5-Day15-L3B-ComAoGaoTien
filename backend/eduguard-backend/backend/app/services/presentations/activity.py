from typing import Optional, Dict, Any, List
from uuid import UUID

from app.models.presentation import PresentationActivity
from app.services.base import BaseService


class ActivityService(BaseService):

    def log(self, presentation_id: UUID, user_id: int, activity_type: str,
            activity_data: Dict[str, Any], description: Optional[str] = None):

        activity = PresentationActivity(
            presentation_id=presentation_id,
            user_id=user_id,
            activity_type=activity_type,
            activity_data=activity_data,
            description=description or f"User {activity_type} presentation"
        )
        self.db.add(activity)