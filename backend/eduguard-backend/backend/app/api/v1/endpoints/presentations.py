from uuid import UUID
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.services.presentations import PresentationService
from app.schemas.presentation import (
    ConfigData,
    PresentationCreate, PresentationUpdate, PresentationResponse,
    PresentationPageCreateRequest, PresentationPageUpdate, PresentationPageResponse,
    CommentCreate, CommentResponse, ShareCreate, ShareResponse
)
from app.utils.pptx_utils import parse_cover_url, encode_response_data, normalize_element_positions

router = APIRouter()


@router.get("/config/options")
async def config_options():
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "tone": ConfigData.tone,
            "style": ConfigData.style,
            "audience": ConfigData.audience,
            "language": ConfigData.language,
            "model": ConfigData.model,
            "slide_count": ConfigData.slide_count
        }
    }


@router.post("", response_model=PresentationResponse)
async def create_presentation(
        presentation_data: PresentationCreate,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.create_presentation(presentation_data, current_user.id)


@router.get("")
async def get_user_presentations(
        request: Request,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    results = service.list_presentations(current_user.id, page, limit)

    presentations = []
    if results:
        for tpl in results["presentations"]:
            tpl_dict = tpl.to_dict() if hasattr(tpl, 'to_dict') else vars(tpl)

            tpl_dict["owner_name"] = tpl.owner.username if hasattr(tpl, 'owner') and tpl.owner else None
            tpl_dict["template_name"] = tpl.template.name if hasattr(tpl, 'template') and tpl.template else None
            tpl_dict["cover_url"] = parse_cover_url(request, tpl_dict.get("cover_url"))

            presentations.append(tpl_dict)

        return {
            **results,
            "presentations": presentations
        }

    return results


@router.get("/{presentation_id}")
async def get_user_presentation(
        request: Request,
        presentation_id: UUID,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    presentation = service.get_presentation(presentation_id, current_user.id)

    presentation_dict = presentation.to_dict() if hasattr(presentation, "to_dict") else vars(presentation)

    presentation_dict["cover_url"] = parse_cover_url(request, presentation_dict.get("cover_url"))
    presentation_dict["owner_name"] = presentation.owner.username if hasattr(presentation, 'owner') and presentation.owner else None
    presentation_dict["template_name"] = presentation.template.name if hasattr(presentation, 'template') and presentation.template else None

    slides = []
    if hasattr(presentation, 'pages') and presentation.pages:
        active_pages = [page for page in presentation.pages if page.is_active]
        sorted_pages = sorted(active_pages, key=lambda p: p.page_order or 0)

        slides = [
            {
                "id": str(page.id),
                "page_order": page.page_order,
                "type": page.page_type,
                "elements": page.page_data,
                "background": page.background or {
                    "type": "solid",
                    "color": "#ffffff"
                }
            }
            for page in sorted_pages
        ]

    presentation_dict["pptxProperty"] = encode_response_data({"slides": slides})
    presentation_dict["total_pages"] = len(slides)

    return presentation_dict


@router.put("/{presentation_id}")
async def update_user_presentation(
        request: Request,
        presentation_id: UUID,
        presentation_data: PresentationUpdate,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    _ = service.update_presentation(presentation_id, presentation_data, current_user.id)

    return {"message": "Presentation updated successfully"}


@router.delete("/{presentation_id}")
async def delete_presentation(
        request: Request,
        presentation_id: UUID,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    service.delete_presentation(presentation_id, current_user.id)
    return {"message": "Presentation deleted successfully"}


@router.post("/{presentation_id}/clone", include_in_schema=False, response_model=PresentationResponse)
async def clone_presentation(
        request: Request,
        presentation_id: UUID,
        new_title: Optional[str] = None,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.clone_presentation(presentation_id, current_user.id, new_title)


@router.get("/{presentation_id}/pages", response_model=List[PresentationPageResponse])
async def get_presentation_pages(
        request: Request,
        presentation_id: UUID,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.get_presentation_pages(presentation_id, current_user.id)


@router.post("/{presentation_id}/pages")
async def create_presentation_page(
        request: Request,
        presentation_id: UUID,
        page_data: PresentationPageCreateRequest,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    page_data.presentation_id = presentation_id

    # Normalize element positions if source dimensions are provided
    if page_data.source_width and page_data.source_height:
        page_data.elements = normalize_element_positions(
            page_data.elements,
            page_data.source_width,
            page_data.source_height
        )

    service = PresentationService(db)
    page = service.create_page(page_data, current_user.id)
    data = {
        "message": "Page create successfully",
        "data": {
            "id": page.id,
            "type": page.page_type
        }
    }
    return data


@router.put("/pages/{page_id}", response_model=PresentationPageResponse)
async def update_presentation_page(
        request: Request,
        page_id: UUID,
        page_data: PresentationPageUpdate,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.update_page(page_id, page_data, current_user.id)


@router.delete("/pages/{page_id}")
async def delete_presentation_page(
        request: Request,
        page_id: UUID,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    service.delete_page(page_id, current_user.id)
    return {"message": "Page deleted successfully"}


@router.post("/{presentation_id}/comments", response_model=CommentResponse)
async def create_presentation_comment(
        request: Request,
        presentation_id: UUID,
        comment_data: CommentCreate,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.create_comment(presentation_id, comment_data, current_user.id)


@router.get("/{presentation_id}/comments", response_model=List[CommentResponse])
async def get_presentation_comments(
        request: Request,
        presentation_id: UUID,
        page_id: Optional[UUID] = Query(None),
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.get_comments(presentation_id, page_id, current_user.id)


@router.post("/{presentation_id}/shares", response_model=ShareResponse)
async def create_presentation_share(
        request: Request,
        presentation_id: UUID,
        share_data: ShareCreate,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)
):
    service = PresentationService(db)
    return service.create_share(presentation_id, share_data, current_user.id)
