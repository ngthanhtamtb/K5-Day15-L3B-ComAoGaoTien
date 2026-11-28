"""Column types that work on both SQLite (dev/test) and PostgreSQL (prod).

The original RAGslides models imported `JSONB` / `UUID` from the postgresql dialect, which
made SQLite impossible. Models now import `JSONB` and `UUID` from here instead:
  * JSONB -> JSON everywhere, JSONB on PostgreSQL (keeps GIN-indexable columns in prod)
  * UUID(as_uuid=True) -> sqlalchemy.Uuid (native uuid on PostgreSQL, CHAR(32) on SQLite)
"""
from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects import postgresql

JSONB = JSON().with_variant(postgresql.JSONB(), "postgresql")


def UUID(as_uuid: bool = True):  # noqa: N802 — keeps the call sites `UUID(as_uuid=True)` unchanged
    return Uuid(as_uuid=as_uuid)
