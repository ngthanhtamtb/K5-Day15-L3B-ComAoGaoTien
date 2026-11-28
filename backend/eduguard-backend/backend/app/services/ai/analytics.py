from typing import Dict, Any
import logging

from app.services.ai.base import BaseAIService

logger = logging.getLogger(__name__)


class AIAnalyticsService(BaseAIService):

    async def get_user_token_usage(self, user_id: int) -> Dict[str, Any]:
        return await self.token_tracker.get_user_token_usage(user_id)

    async def get_usage_summary(self, user_id: int, period: str = "30d") -> Dict[str, Any]:
        usage_data = await self.token_tracker.get_user_token_usage(user_id)

        summary = {
            "total_tokens": usage_data.get("total_tokens", 0),
            "operations_count": usage_data.get("operations_count", 0),
            "most_used_operation": usage_data.get("most_used_operation", "N/A"),
            "period": period
        }

        return summary

    async def get_system_analytics(self) -> Dict[str, Any]:
        pass