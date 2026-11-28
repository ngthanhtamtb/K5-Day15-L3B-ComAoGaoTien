import traceback
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User
from app.models.token_tracker import TokenUsage
import logging

logger = logging.getLogger(__name__)


class TokenTracker:

    async def track_token_usage(
            self,
            user_id: int,
            operation_type: str,
            token_counts: Dict[str, int],
            operation_data: Dict[str, Any] = None
    ):
        db: Session = SessionLocal()
        try:
            prompt_tokens = int(token_counts.get('prompt_tokens', 0) or 0)
            completion_tokens = int(token_counts.get('completion_tokens', 0) or 0)

            thoughts_tokens = int(
                token_counts.get('internal_thinking_tokens', 0) or
                token_counts.get('thoughts_token_count', 0) or 0
            )
            total_tokens = int(token_counts.get('total_tokens', 0) or 0)
            cached_tokens = int(token_counts.get('cached_tokens', 0) or 0)

            if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
                total_tokens = prompt_tokens + completion_tokens + thoughts_tokens

            if total_tokens == 0:
                logger.warning(f"Total tokens is 0 for user {user_id}, operation {operation_type}. Skipping DB insert.")
                return

            usage_record = TokenUsage(
                user_id=user_id,
                operation_type=operation_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                thoughts_tokens=thoughts_tokens,
                total_tokens=total_tokens,
                operation_data=operation_data or {}
            )
            db.add(usage_record)

            user = db.query(User).filter(User.id == user_id).with_for_update().first()
            if user:
                if user.usage_stats is None:
                    user.usage_stats = {}

                current_stats = dict(user.usage_stats)

                current_stats['total_tokens_used'] = current_stats.get('total_tokens_used', 0) + total_tokens
                current_stats['prompt_tokens_used'] = current_stats.get('prompt_tokens_used', 0) + prompt_tokens
                current_stats['completion_tokens_used'] = current_stats.get('completion_tokens_used',
                                                                            0) + completion_tokens
                current_stats['ai_generations'] = current_stats.get('ai_generations', 0) + 1

                user.usage_stats = current_stats
                db.add(user)
            else:
                print(f"⚠️  User {user_id} not found")

            db.commit()
            # print(f"✅ SUCCESS: Token usage tracked for user {user_id}: {total_tokens} tokens")
            # logger.info(f"Token usage tracked for user {user_id}: {usage_record.total_tokens} tokens.")

        except Exception as e:
            db.rollback()
            # print(f"❌ ERROR: Failed to track token usage: {e}")
            # logger.error(f"Failed to track token usage for user {user_id}: {e}", exc_info=True)
            traceback.print_exc()
        finally:
            db.close()

    async def get_user_token_usage(
            self,
            user_id: int,
            operation_type: Optional[str] = None,
            limit: int = 100
    ) -> Dict[str, Any]:
        db: Session = SessionLocal()
        try:
            query = db.query(TokenUsage).filter(TokenUsage.user_id == user_id)

            if operation_type:
                query = query.filter(TokenUsage.operation_type == operation_type)

            usage_records = query.order_by(TokenUsage.created_at.desc()).limit(limit).all()

            total_prompt_tokens = sum(record.prompt_tokens for record in usage_records)
            total_completion_tokens = sum(record.completion_tokens for record in usage_records)
            total_tokens = sum(record.total_tokens for record in usage_records)

            return {
                "usage_history": [
                    {
                        "operation_type": record.operation_type,
                        "prompt_tokens": record.prompt_tokens,
                        "completion_tokens": record.completion_tokens,
                        "total_tokens": record.total_tokens,
                        "created_at": record.created_at,
                        "operation_data": record.operation_data
                    }
                    for record in usage_records
                ],
                "summary": {
                    "total_prompt_tokens": total_prompt_tokens,
                    "total_completion_tokens": total_completion_tokens,
                    "total_tokens": total_tokens,
                    "total_operations": len(usage_records)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get user token usage: {e}")
            return {"usage_history": [], "summary": {}}
        finally:
            db.close()

    async def get_operation_stats(self, operation_type: str) -> Dict[str, Any]:
        db: Session = SessionLocal()
        try:
            records = db.query(TokenUsage).filter(
                TokenUsage.operation_type == operation_type
            ).all()

            if not records:
                return {"count": 0, "average_tokens": 0, "total_tokens": 0}

            total_tokens = sum(record.total_tokens for record in records)
            average_tokens = total_tokens / len(records)

            return {
                "count": len(records),
                "average_tokens": round(average_tokens, 2),
                "total_tokens": total_tokens,
                "average_prompt_tokens": round(sum(r.prompt_tokens for r in records) / len(records), 2),
                "average_completion_tokens": round(sum(r.completion_tokens for r in records) / len(records), 2)
            }
        except Exception as e:
            logger.error(f"Failed to get operation stats: {e}")
            return {"count": 0, "average_tokens": 0, "total_tokens": 0}
        finally:
            db.close()
