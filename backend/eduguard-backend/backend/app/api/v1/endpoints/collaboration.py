from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.presentation import Presentation
from app.schemas.presentation import (
    CollaboratorInvite, CollaboratorResponse
)
from app.services.presentations import PresentationService

router = APIRouter()


@router.post("/{presentation_id}/collaborators", response_model=CollaboratorResponse)
async def invite_collaborator(
    presentation_id: UUID,
    invite_data: CollaboratorInvite,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.invite_collaborator(presentation_id, invite_data, current_user.id)

@router.post("/collaborations/accept/{invite_token}", response_model=CollaboratorResponse)
async def accept_collaboration(
    invite_token: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.accept_collaboration(invite_token, current_user.id)


@router.post("/presentations/{presentation_id}/share")
async def share_presentation(
        presentation_id: int,
        share_settings: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id,
        Presentation.owner_id == current_user.id
    ).first()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    if "is_public" in share_settings:
        presentation.is_public = share_settings["is_public"]

    if "public_token" in share_settings:
        presentation.public_token = share_settings["public_token"]

    db.commit()

    return {"message": "Sharing settings updated",
            "public_url": f"/public/{presentation.public_token}" if presentation.public_token else None}


@router.get("/presentations/{presentation_id}/share-settings")
async def get_share_settings(
        presentation_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id,
        Presentation.owner_id == current_user.id
    ).first()

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")

    return {
        "is_public": presentation.is_public,
        "public_token": presentation.public_token,
        "public_url": f"/public/{presentation.public_token}" if presentation.public_token else None
    }
