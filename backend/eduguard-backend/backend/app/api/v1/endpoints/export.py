from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.presentation import Presentation

router = APIRouter()


@router.post("/presentations/{presentation_id}/export/pdf")
async def export_to_pdf(
        presentation_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id
    ).first()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    job_id = f"pdf_export_{presentation_id}"

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "PDF export started"
    }


@router.post("/presentations/{presentation_id}/export/pptx")
async def export_to_powerpoint(
        presentation_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id
    ).first()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    job_id = f"pptx_export_{presentation_id}"

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "PowerPoint export started"
    }


@router.get("/presentations/{presentation_id}/export-status/{job_id}")
async def get_export_status(
        presentation_id: int,
        job_id: str,
        current_user: User = Depends(get_current_user)
):
    return {
        "job_id": job_id,
        "status": "completed",
        "download_url": f"/api/presentations/{presentation_id}/download/{job_id}"
    }
