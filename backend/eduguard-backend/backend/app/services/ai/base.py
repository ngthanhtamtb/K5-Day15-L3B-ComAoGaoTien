import json
import logging
from abc import ABC
from typing import Dict, Any, Optional

from app.core.pptagent.llm_client import TokenCollectorHandler
from app.services.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


class BaseAIService(ABC):
    def __init__(self):
        self.token_collector = TokenCollectorHandler()
        self.token_tracker = TokenTracker()

    def _extract_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != -1:
                json_content = content[start:end]
                return json.loads(json_content)
            return None
        except json.JSONDecodeError:
            logger.warning("Failed to decode JSON from AI response.")
            return None

    async def _track_token_usage(self, user_id: int, operation_type: str,
                                 token_usage: Dict[str, int], operation_data: Dict[str, Any] = None):
        try:
            if not token_usage or token_usage.get('total_tokens', 0) <= 0:
                return

            await self.token_tracker.track_token_usage(
                user_id=user_id,
                operation_type=operation_type,
                token_counts=token_usage,
                operation_data=operation_data
            )
        except Exception as e:
            logger.error(f"Failed to track token usage for user {user_id}: {e}")
