from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.user import UserResponse, UserUpdate, UserUsage, UserActivity

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return UserResponse.model_validate(current_user)


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/avatar")
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    avatar_url = f"/uploads/avatars/{current_user.id}_{file.filename}"
    current_user.avatar_url = avatar_url
    db.commit()

    return {"avatar_url": avatar_url}


@router.get("/subscription")
async def get_subscription(current_user: User = Depends(get_current_user)):
    return {
        "subscription_type": current_user.subscription_type,
        "expires": current_user.subscription_expires,
        "features": {
            "max_presentations": 100 if current_user.subscription_type == "pro" else 10,
            "ai_generations_per_month": 1000 if current_user.subscription_type == "pro" else 50,
            "storage_limit_gb": 10 if current_user.subscription_type == "pro" else 1
        }
    }


@router.get("/usage", response_model=UserUsage)
async def get_usage(current_user: User = Depends(get_current_user)):
    return UserUsage(
        presentations_created=len(current_user.presentations),
        ai_generations_used=current_user.usage_stats.get("ai_generations", 0),
        storage_used=current_user.usage_stats.get("storage_used", 0),
        monthly_limit=1000 if current_user.subscription_type == "pro" else 50
    )


@router.get("/activity", response_model=UserActivity)
async def get_activity(current_user: User = Depends(get_current_user)):
    return UserActivity(
        recent_presentations=[],
        recent_ai_generations=[],
        login_history=[]
    )


@router.get("/notifications")
async def get_notifications(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return notifications


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
        notification_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    return {"message": "Notification marked as read"}
