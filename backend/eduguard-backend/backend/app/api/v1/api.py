from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, presentations, templates, ai, media, collaboration, export, analytics, admin, document, edu,
    edu_flow,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(presentations.router, prefix="/presentations", tags=["presentations"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(document.router, prefix="/document", tags=["Document"])
api_router.include_router(collaboration.router, prefix="/collaboration", tags=["collaboration"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(edu.router, prefix="/edu", tags=["EduGuard"])
api_router.include_router(edu_flow.router, prefix="/edu", tags=["EduGuard · review flow"])
