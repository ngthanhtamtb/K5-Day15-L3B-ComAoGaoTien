from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.presentation import Presentation
from app.models.template import Template

router = APIRouter()

async def get_admin_user(current_user: User = Depends(get_current_user)):
    from app.edu.billing import is_admin
    if not is_admin(current_user):          # role=admin or email listed in ADMIN_EMAILS
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class SetPlanBody(BaseModel):
    subscription_type: Optional[str] = None   # e.g. free | premium | pho_thong | tra_phi
    role: Optional[str] = None                # admin | giang_vien | bien_tap | nguoi_dung


@router.put("/users/{user_id}/plan", summary="Admin assigns a plan / role by hand (no payment yet)")
async def set_user_plan(user_id: int, body: SetPlanBody, admin_user: User = Depends(get_admin_user),
                        db: Session = Depends(get_db)):
    from app.edu.billing import ROLES, load_plans, plan_id_for
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "user not found")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(400, f"role must be one of {', '.join(ROLES)}")
        user.role = body.role
    if body.subscription_type is not None:
        plans = load_plans().get("plans") or {}
        if plan_id_for(body.subscription_type) not in plans:
            raise HTTPException(400, "unknown plan")
        user.subscription_type = body.subscription_type
    db.commit()
    return {"id": user.id, "role": user.role, "subscriptionType": user.subscription_type,
            "planId": plan_id_for(user.subscription_type)}

@router.get("/users")
async def get_all_users(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return users

@router.get("/presentations")
async def get_all_presentations(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    presentations = db.query(Presentation).all()
    return presentations

@router.get("/system-health")
async def get_system_health(admin_user: User = Depends(get_admin_user)):
    return {
        "status": "healthy",
        "database": "connected",
        "ai_service": "operational",
        "storage": "available"
    }
