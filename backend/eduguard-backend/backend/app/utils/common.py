import uuid
import time
import secrets
from sqlalchemy.inspection import inspect


def _generate_nanoid(length: int = 10) -> str:
    return str(uuid.uuid4())[:length]


def generate_numeric_id() -> str:
    return str(int(time.time() * 1e6))


def generate_user_token(prefix="sk-", length=34) -> str:
    return prefix + secrets.token_urlsafe(length)[:length]


def to_dict(obj):
    return {c.key: getattr(obj, c.key)for c in inspect(obj).mapper.column_attrs}