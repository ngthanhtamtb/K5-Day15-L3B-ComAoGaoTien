"""Roles + plans framework (pho_thong / tra_phi). Recording only unless BILLING_ENFORCE=true.

In an endpoint:
    ctx: PlanContext = Depends(plan_context)
    ctx.require("ocr")                       # no-op now; 402 when enforced and the plan lacks it
    warn = ctx.consume("voice_chars", 6200)  # always recorded; returns a warning string if over quota
"""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

ROLES = ("admin", "giang_vien", "bien_tap", "nguoi_dung")
_optional_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def load_plans() -> Dict[str, Any]:
    path = settings.PLANS_FILE
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {"default_plan": "pho_thong", "aliases": {}, "plans": {"pho_thong": {"features": {}, "quotas": {}}}}


def plan_id_for(subscription_type: Optional[str]) -> str:
    cfg = load_plans()
    key = (subscription_type or "").strip().lower()
    if key in (cfg.get("plans") or {}):
        return key
    return (cfg.get("aliases") or {}).get(key) or cfg.get("default_plan", "pho_thong")


def is_admin(user) -> bool:
    if user is None:
        return False
    admins = {e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()}
    return getattr(user, "role", None) == "admin" or (getattr(user, "email", "") or "").lower() in admins


def _period(now: Optional[datetime.date] = None) -> str:
    d = now or datetime.date.today()
    return f"{d.year:04d}-{d.month:02d}"


@dataclass
class PlanContext:
    db: Session
    user: Any = None                      # app.models.user.User or None (anonymous)
    plan_id: str = "pho_thong"
    plan: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    uid: Optional[int] = None             # captured at request time; safe to use after the session closes

    @property
    def user_key(self) -> str:
        return str(self.uid) if self.uid is not None else "anon"

    def for_background(self) -> "PlanContext":
        """Same plan/user with a fresh DB session, for work that outlives the request (jobs)."""
        from app.core.database import SessionLocal
        return PlanContext(db=SessionLocal(), user=None, plan_id=self.plan_id, plan=self.plan, uid=self.uid)

    @property
    def enforced(self) -> bool:
        return bool(settings.BILLING_ENFORCE)

    def feature(self, name: str) -> Any:
        return (self.plan.get("features") or {}).get(name)

    def allows(self, name: str, value: Any = True) -> bool:
        f = self.feature(name)
        if isinstance(f, list):
            return value in f
        return bool(f)

    def require(self, name: str, value: Any = True) -> None:
        if self.allows(name, value):
            return
        msg = f"Tính năng '{name}' không có trong gói {self.plan.get('name', self.plan_id)}"
        if self.enforced:
            raise HTTPException(402, msg)
        self.warnings.append(msg + " (chưa áp dụng chặn)")

    def used(self, metric: str) -> float:
        from .models import UsageCounter
        row = (self.db.query(UsageCounter)
               .filter_by(user_key=self.user_key, metric=metric, period=_period()).first())
        return row.amount if row else 0.0

    def consume(self, metric: str, amount: float) -> Optional[str]:
        """Record usage; return a warning if the plan's monthly quota is exceeded.
        With BILLING_ENFORCE=true the call is refused (402) BEFORE recording."""
        from .models import UsageCounter
        limit = (self.plan.get("quotas") or {}).get(metric)
        before = self.used(metric)
        over = limit is not None and before + amount > float(limit)
        if over and self.enforced:
            raise HTTPException(402, f"Vượt hạn mức {metric}: {before + amount:g}/{limit:g} trong tháng")
        row = (self.db.query(UsageCounter)
               .filter_by(user_key=self.user_key, metric=metric, period=_period()).first())
        if row is None:
            row = UsageCounter(user_key=self.user_key, metric=metric, period=_period(), amount=0)
            self.db.add(row)
        row.amount = (row.amount or 0) + float(amount)
        self.db.commit()
        if over:
            msg = f"Vượt hạn mức {metric}: {before + amount:g}/{limit:g} (chưa áp dụng chặn)"
            self.warnings.append(msg)
            return msg
        return None

    def summary(self) -> Dict[str, Any]:
        quotas = self.plan.get("quotas") or {}
        return {
            "planId": self.plan_id, "planName": self.plan.get("name", self.plan_id),
            "userId": self.uid, "role": getattr(self.user, "role", None) if self.user is not None else None,
            "enforced": self.enforced, "features": self.plan.get("features") or {},
            "usage": {m: {"used": self.used(m), "limit": quotas.get(m)} for m in quotas},
            "period": _period(),
        }


def _user_from_token(creds: Optional[HTTPAuthorizationCredentials], db: Session):
    if creds is None:
        return None
    from jose import JWTError, jwt
    from app.models.user import User
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    uid = payload.get("sub")
    return db.query(User).filter(User.id == uid).first() if uid is not None else None


def plan_context(creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
                 db: Session = Depends(get_db)) -> PlanContext:
    """Optional login: edu routes stay usable without a token (anonymous = default plan)."""
    user = _user_from_token(creds, db)
    cfg = load_plans()
    pid = plan_id_for(getattr(user, "subscription_type", None) if user is not None else None)
    return PlanContext(db=db, user=user, plan_id=pid, plan=(cfg.get("plans") or {}).get(pid, {}),
                       uid=user.id if user is not None else None)
