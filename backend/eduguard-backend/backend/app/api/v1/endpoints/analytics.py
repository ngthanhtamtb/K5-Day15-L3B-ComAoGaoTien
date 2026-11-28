from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from uuid import UUID

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.response import success_response, error_response, ResponseCode
from app.models.user import User
from app.models.template import Template, TemplateUsage
from app.models.presentation import Presentation, PresentationActivity, PresentationCollaborator
from app.services.ai import AIPPTService

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user_id = current_user.id

    template_stats = db.query(
        func.count(Template.id).label("total_templates"),
        func.sum(Template.view_count).label("total_views"),
        func.sum(Template.download_count).label("total_downloads"),
        func.sum(Template.like_count).label("total_likes")
    ).filter(Template.created_by_user_id == user_id).first()

    presentation_stats = db.query(
        func.count(Presentation.id).label("total_presentations"),
        func.sum(Presentation.view_count).label("total_views"),
        func.sum(Presentation.share_count).label("total_shares")
    ).filter(Presentation.owner_id == user_id).first()

    recent_activity = db.query(PresentationActivity).filter(
        PresentationActivity.user_id == user_id
    ).order_by(desc(PresentationActivity.created_at)).limit(10).all()

    return {
        "templates": {
            "total": template_stats.total_templates or 0,
            "total_views": template_stats.total_views or 0,
            "total_downloads": template_stats.total_downloads or 0,
            "total_likes": template_stats.total_likes or 0
        },
        "presentations": {
            "total": presentation_stats.total_presentations or 0,
            "total_views": presentation_stats.total_views or 0,
            "total_shares": presentation_stats.total_shares or 0
        },
        "recent_activity": [
            {
                "id": str(activity.id),
                "type": activity.activity_type,
                "description": activity.description,
                "created_at": activity.created_at
            }
            for activity in recent_activity
        ]
    }


@router.get("/token-usage", response_model=dict)
async def get_token_usage(
        request: Request,
        operation_type: str = Query(None, description="Filter by operation type"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        ai_service = AIPPTService(db)
        usage_data = await ai_service.get_user_token_usage(current_user.id)

        return usage_data

    except Exception as e:
        return error_response(
            message="Failed to retrieve token usage",
            code=ResponseCode.INTERNAL_ERROR,
            errors={"detail": str(e)}
        )


@router.get("/templates/{template_id}/stats")
async def get_template_analytics(
        request: Request,
        template_id: UUID,
        days: int = Query(30, ge=1, le=365),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by_user_id == current_user.id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    start_date = datetime.now() - timedelta(days=days)

    usage_stats = db.query(
        TemplateUsage.action_type,
        func.count(TemplateUsage.id).label("count"),
        func.date(TemplateUsage.used_at).label("date")
    ).filter(
        TemplateUsage.template_id == template_id,
        TemplateUsage.used_at >= start_date
    ).group_by(
        TemplateUsage.action_type,
        func.date(TemplateUsage.used_at)
    ).all()

    stats_by_date = {}
    for stat in usage_stats:
        date_str = stat.date.isoformat()
        if date_str not in stats_by_date:
            stats_by_date[date_str] = {"views": 0, "downloads": 0, "clones": 0}
        stats_by_date[date_str][stat.action_type + "s"] = stat.count

    return {
        "template_id": str(template_id),
        "period_days": days,
        "total_stats": {
            "views": template.view_count,
            "downloads": template.download_count,
            "likes": template.like_count,
            "clones": template.clone_count
        },
        "daily_stats": stats_by_date
    }


@router.get("/presentations/{presentation_id}/stats")
async def get_presentation_analytics(
        request: Request,
        presentation_id: UUID,
        days: int = Query(30, ge=1, le=365),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id
    ).first()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    if presentation.owner_id != current_user.id:
        collaborator = db.query(PresentationCollaborator).filter(
            PresentationCollaborator.presentation_id == presentation_id,
            PresentationCollaborator.user_id == current_user.id,
            PresentationCollaborator.status == "accepted"
        ).first()

        if not collaborator:
            raise HTTPException(status_code=403, detail="Access denied")

    start_date = datetime.now() - timedelta(days=days)

    activity_stats = db.query(
        PresentationActivity.activity_type,
        func.count(PresentationActivity.id).label("count"),
        func.date(PresentationActivity.created_at).label("date")
    ).filter(
        PresentationActivity.presentation_id == presentation_id,
        PresentationActivity.created_at >= start_date
    ).group_by(
        PresentationActivity.activity_type,
        func.date(PresentationActivity.created_at)
    ).all()

    return {
        "presentation_id": str(presentation_id),
        "period_days": days,
        "total_stats": {
            "views": presentation.view_count,
            "shares": presentation.share_count,
            "clones": presentation.clone_count,
            "pages": presentation.page_count
        },
        "activity_stats": [
            {
                "type": stat.activity_type,
                "count": stat.count,
                "date": stat.date.isoformat()
            }
            for stat in activity_stats
        ]
    }


@router.get("/popular-templates")
async def get_popular_templates(
        request: Request,
        period: str = Query("week", regex="^(day|week|month|year)$"),
        limit: int = Query(10, ge=1, le=50),
        db: Session = Depends(get_db)
):
    now = datetime.now()
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:  # year
        start_date = now - timedelta(days=365)

    popular_templates = db.query(
        Template.id,
        Template.name,
        Template.category,
        Template.view_count,
        Template.download_count,
        Template.like_count,
        func.sum(
            case(
                (TemplateUsage.action_type == "view", 1),
                else_=0
            )
        ).label("period_views"),
        func.sum(
            case(
                (TemplateUsage.action_type == "download", 3),
                (TemplateUsage.action_type == "clone", 2),
                (TemplateUsage.action_type == "view", 1),
                else_=0
            )
        ).label("popularity_score")
    ).join(
        TemplateUsage, Template.id == TemplateUsage.template_id
    ).filter(
        Template.is_active == True,
        Template.is_public == True,
        TemplateUsage.used_at >= start_date
    ).group_by(
        Template.id
    ).order_by(
        desc("popularity_score")
    ).limit(limit).all()

    return {
        "period": period,
        "templates": [
            {
                "id": str(template.id),
                "name": template.name,
                "category": template.category,
                "total_views": template.view_count,
                "total_downloads": template.download_count,
                "total_likes": template.like_count,
                "period_views": template.period_views,
                "popularity_score": template.popularity_score
            }
            for template in popular_templates
        ]
    }


@router.get("/trending-categories")
async def get_trending_categories(
        request: Request,
        days: int = Query(7, ge=1, le=30),
        db: Session = Depends(get_db)
):
    start_date = datetime.now() - timedelta(days=days)

    category_stats = db.query(
        Template.category,
        func.count(TemplateUsage.id).label("usage_count"),
        func.count(func.distinct(Template.id)).label("template_count")
    ).join(
        TemplateUsage, Template.id == TemplateUsage.template_id
    ).filter(
        Template.is_active == True,
        Template.is_public == True,
        TemplateUsage.used_at >= start_date
    ).group_by(
        Template.category
    ).order_by(
        desc("usage_count")
    ).all()

    return {
        "period_days": days,
        "categories": [
            {
                "category": stat.category,
                "usage_count": stat.usage_count,
                "template_count": stat.template_count
            }
            for stat in category_stats
        ]
    }
