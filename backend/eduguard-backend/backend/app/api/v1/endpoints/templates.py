import os
import traceback
import uuid
import json
from typing import Optional, Any, Dict, Union
from fastapi import (
    APIRouter, Request, Depends, HTTPException, status as http_status, Query, File, Form, UploadFile
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.services.templates import TemplateService
from app.models.user import User
from app.models.template import TemplatePage
from app.core.pptagent.types import (
    TemplateCategoryType, TemplateType, TemplateStatusType, PageScopeType, PageType, PageSectionType, PageCategoryType
)
from app.core.pptagent.filters import MultiLanguageTemplateFilters
from app.schemas.template import (
    TemplateCreateRequest, TemplateListResponse, TemplateReviewRequest, TemplatePageUpdateRequest, TemplatePageCreateRequest,
    TemplateUpdateRequest, TemplateCollectionRequest, TemplateReportRequest, TemplateSearchParams
)
from app.utils.pptx_utils import parse_cover_url, handle_thumbnail_upload, encode_response_data, normalize_slides_data

router = APIRouter()


@router.get("/slide/filters", response_model=Dict[str, Any])
async def get_slide_filters(language: Optional[str] = Query("en", description="Language code: vi, en, ja")):
    config = MultiLanguageTemplateFilters(default_language="en")

    if language not in config.supported_languages:
        language = config.default_language

    page_type_groups = config.get_page_type_groups(language)

    page_categories = []
    for category in PageCategoryType:
        category_label = category.value.replace("_", " ").title()
        if language == "en":
            category_labels = {
                "structure": "Structure",
                "component": "Component",
                "scene": "Scene"
            }
            category_label = category_labels.get(category.value, category_label)
        elif language == "vi":
            category_labels = {
                "structure": "Cấu trúc",
                "component": "Thành phần",
                "scene": "Tình huống"
            }
            category_label = category_labels.get(category.value, category_label)
        elif language == "ja":
            category_labels = {
                "structure": "構造",
                "component": "コンポーネント",
                "scene": "シーン"
            }
            category_label = category_labels.get(category.value, category_label)

        page_categories.append({
            "value": category.value,
            "label": category_label,
            "section_types": page_type_groups[category]
        })

    return {
        "page_categories": page_categories,
        "page_scope_types": config.get_scope_types(language),
        "page_types": config.get_page_types(language)
    }


@router.post("/create/template")
async def create_template(
        template_data: str = Form(...),
        cover_file: Optional[UploadFile] = File(None),
        template_type: Optional[TemplateType] = Form(None),
        category: str = Form(None),
        tags: str = Form(None),
        keywords: str = Form(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        template_json = json.loads(template_data)

        if not template_json.get("title"):
            raise HTTPException(status_code=400, detail="Template title is required")

        cover_url = None
        if cover_file:
            allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
            if cover_file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
                )

            file_extension = cover_file.filename.split(".")[-1] if "." in cover_file.filename else "jpg"
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            # cover_path = settings.UPLOAD_TEMPLATES_DIR / unique_filename

            # with open(cover_path, "wb") as buffer:
            #     content = await cover_file.read()
            #     buffer.write(content)

            cover_url = f"/uploads/templates/{unique_filename}"

        template_info = {
            "name": template_json.get("title", ""),
            "subject": None,
            "description": None,
            "width": 1000,
            "height": 562.5,
            "cover_url": cover_url,
            "file_url": None,
            "template_type": template_type.strip().lower() if template_type else TemplateType.USER,
            "category": "presentation",
            "tags": [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else ["presentation", "slides"],
            "keywords": [kws.strip() for kws in keywords.split(",") if kws.strip()] if keywords else ["presentation",
                                                                                                      "template"],
            "difficulty_level": 1,
            "estimated_time": len(template_json.get("slides", [])) * 5,
            "is_premium": False,
            "price": 0.0,
            "ext_info": {
                "slides_count": len(template_json.get("slides", [])),
            }
        }

        service = TemplateService(db)
        template = service.create_template_with_pages(template_info, current_user.id, template_json.get("slides", []))

        # if template_json:
        #     json_filename = f"{template.id}_data.json"
        #     json_path = UPLOAD_DIR / json_filename
        #     with open(json_path, "w", encoding="utf-8") as f:
        #         json.dump(template_json, f, ensure_ascii=False, indent=2)
        #
        #     template.file_url = f"/uploads/templates/{json_filename}"
        #     db.add(template)
        #     db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "template": {
                    "id": str(template.id),
                    "name": template.name,
                    "cover_url": template.cover_url,
                    "slides_count": len(template_json.get("slides", [])),
                    "pages_count": len(template.pages) if hasattr(template, 'pages') else len(
                        template_json.get("slides", [])),
                    "created_at": template.created_at.isoformat() if template.created_at else None
                },
                "message": "Template created successfully with pages"
            }
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in template_data")
    except Exception as e:
        if cover_url and os.path.exists(settings.UPLOAD_TEMPLATES_DIR / cover_url.split("/")[-1]):
            os.remove(settings.UPLOAD_TEMPLATES_DIR / cover_url.split("/")[-1])

        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")


@router.get("/{template_id}")
async def get_template(
        request: Request,
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
) -> Union[Dict[str, Any], None]:
    service = TemplateService(db)
    tpl = service.get_template(template_id, current_user.id)

    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")

    tpl_dict = tpl.to_dict() if hasattr(tpl, "to_dict") else vars(tpl)
    tpl_dict["cover_url"] = parse_cover_url(request, tpl_dict.get("cover_url"))

    return tpl_dict


@router.get("/{template_id}/detailed")
async def get_template_detailed(
        request: Request,
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
) -> Union[Dict[str, Any], None]:
    service = TemplateService(db)
    template = service.get_template(template_id, current_user.id)

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    template_dict = template.to_dict() if hasattr(template, "to_dict") else vars(template)
    template_dict["cover_url"] = parse_cover_url(request, template_dict.get("cover_url"))

    slides = []
    if hasattr(template, 'pages') and template.pages:
        active_pages = [page for page in template.pages if page.is_active]
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

    template_dict["pptxProperty"] = encode_response_data({"slides": slides})
    template_dict["total_pages"] = len(slides)
    return template_dict


@router.put("/{template_id}")
async def update_template(
        request: Request,
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Update template - supports multipart/form-data with file upload.
    Frontend sends:
    - cover_files: single cover image
    - thumbnail_files: multiple thumbnail images (one per slide)
    - template_data: JSON string with slides and title
    """
    print(f"=== UPDATE TEMPLATE DEBUG ===")
    print(f"template_id: {template_id}")
    print(f"current_user: {current_user.id}")

    # Parse multipart form data manually with increased size limit
    # Default is 1MB (1024 * 1024), increase to 50MB per part
    try:
        max_part_size = 50 * 1024 * 1024  # 50MB
        form_data = await request.form(max_part_size=max_part_size)
        print(f"Form data keys: {list(form_data.keys())}")
    except Exception as e:
        print(f"Error parsing form data: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error parsing form data: {str(e)}")

    # Get form fields
    template_data = form_data.get("template_data")
    cover_files = form_data.get("cover_files")
    name = form_data.get("name")
    subject = form_data.get("subject")
    description = form_data.get("description")
    category = form_data.get("category")
    tags = form_data.get("tags")
    keywords = form_data.get("keywords")
    difficulty_level_str = form_data.get("difficulty_level")
    difficulty_level = int(difficulty_level_str) if difficulty_level_str else None
    estimated_time_str = form_data.get("estimated_time")
    estimated_time = int(estimated_time_str) if estimated_time_str else None
    is_premium_str = form_data.get("is_premium")
    is_premium = is_premium_str.lower() == "true" if is_premium_str else None
    price_str = form_data.get("price")
    price = float(price_str) if price_str else None
    is_public_str = form_data.get("is_public")
    is_public = is_public_str.lower() == "true" if is_public_str else None

    # Get all thumbnail files
    thumbnail_files = form_data.getlist("thumbnail_files")

    print(f"template_data type: {type(template_data)}")
    print(f"cover_files type: {type(cover_files)}")
    print(f"thumbnail_files count: {len(thumbnail_files)}")

    service = TemplateService(db)
    update_data = {}
    thumbnail_urls = []

    # Handle cover file upload
    if cover_files:
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/octet-stream"]
        if cover_files.content_type and cover_files.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cover file type. Allowed types: {', '.join(allowed_types)}"
            )

        file_extension = "jpg"
        if cover_files.filename and "." in cover_files.filename:
            file_extension = cover_files.filename.split(".")[-1]

        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        cover_url = f"/uploads/templates/{unique_filename}"
        update_data["cover_url"] = cover_url

        # Save file to disk
        from pathlib import Path
        upload_dir = Path(settings.UPLOAD_TEMPLATES_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        cover_path = upload_dir / unique_filename
        with open(cover_path, "wb") as buffer:
            content = await cover_files.read()
            buffer.write(content)
        print(f"Saved cover file to: {cover_path}")

    # Handle thumbnail files upload
    if thumbnail_files:
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/octet-stream"]
        from pathlib import Path
        thumbnail_dir = Path(settings.UPLOAD_PAGE_DIR)
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        for thumbnail_file in thumbnail_files:
            if thumbnail_file.content_type and thumbnail_file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid thumbnail file type. Allowed types: {', '.join(allowed_types)}"
                )

            file_extension = "jpg"
            if thumbnail_file.filename and "." in thumbnail_file.filename:
                file_extension = thumbnail_file.filename.split(".")[-1]

            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            thumbnail_url = f"/uploads/pages/{unique_filename}"
            thumbnail_urls.append(thumbnail_url)

            # Save file to disk
            thumbnail_path = thumbnail_dir / unique_filename
            with open(thumbnail_path, "wb") as buffer:
                content = await thumbnail_file.read()
                buffer.write(content)
            print(f"Saved thumbnail file to: {thumbnail_path}")

    # Handle template data (slides)
    if template_data:
        try:
            template_json = json.loads(template_data)
            slides = template_json.get("slides", [])
            title = template_json.get("title")

            # Get source dimensions for normalization
            source_width = template_json.get("source_width") or template_json.get("width")
            source_height = template_json.get("source_height") or template_json.get("height")

            # Normalize slide positions if source dimensions are provided
            if source_width and source_height:
                slides = normalize_slides_data(slides, source_width, source_height)

            # Update title if provided
            if title:
                update_data["name"] = title

            # Update pages if slides data provided
            if slides:
                # Delete existing pages
                existing_pages = db.query(TemplatePage).filter(
                    TemplatePage.template_id == template_id
                ).all()
                for page in existing_pages:
                    db.delete(page)
                db.flush()

                # Create new pages with thumbnails
                for idx, slide in enumerate(slides):
                    thumbnail_url = thumbnail_urls[idx] if idx < len(thumbnail_urls) else None

                    page = TemplatePage(
                        template_id=template_id,
                        page_data=slide.get("elements", []),
                        page_type=PageType.CONTENT,
                        page_order=slide.get("page_order", idx),
                        background=slide.get("background"),
                        thumbnail_url=thumbnail_url,
                        is_active=True
                    )
                    db.add(page)

                db.flush()
                update_data["ext_info"] = {"slides_count": len(slides)}

                # Update estimated time based on slide count
                if "estimated_time" not in update_data:
                    update_data["estimated_time"] = len(slides) * 5

        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in template_data")

    # Handle other fields (these can override template_data values)
    if name is not None:
        update_data["name"] = name
    if subject is not None:
        update_data["subject"] = subject
    if description is not None:
        update_data["description"] = description
    if category is not None:
        update_data["category"] = category
    if tags is not None:
        update_data["tags"] = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if keywords is not None:
        update_data["keywords"] = [kw.strip() for kw in keywords.split(",") if kw.strip()]
    if difficulty_level is not None:
        update_data["difficulty_level"] = difficulty_level
    if estimated_time is not None:
        update_data["estimated_time"] = estimated_time
    if is_premium is not None:
        update_data["is_premium"] = is_premium
    if price is not None:
        update_data["price"] = price
    if is_public is not None:
        update_data["is_public"] = is_public

    # Update template
    if update_data:
        template = service.update_template(template_id, update_data, current_user.id)
    else:
        # If no update data, just fetch the template
        template = service.get_template(template_id, current_user.id)

    return {"template": template}


@router.delete("/{template_id}")
async def delete_template(
        request: Request,
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    success = service.delete_template(template_id, current_user.id)

    return {"success": success}


@router.get("")
async def get_list_templates(
        request: Request,
        query: Optional[str] = None,
        category: Optional[TemplateCategoryType] = None,
        template_type: Optional[TemplateType] = None,
        status: Optional[TemplateStatusType] = None,
        tags: Optional[str] = Query(None, description="Comma-separated tags"),
        is_featured: Optional[bool] = None,
        is_premium: Optional[bool] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user)
):
    service = TemplateService(db)
    tag_list = tags.split(",") if tags else None

    params = TemplateSearchParams(
        query=query,
        category=category,
        template_type=template_type,
        status=status,
        tags=tag_list,
        is_featured=is_featured,
        is_premium=is_premium,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size
    )

    results = service.search_templates(user_id=current_user.id, params=params)

    result_templates = []
    for tpl in results["templates"]:
        tpl["cover_url"] = parse_cover_url(request, tpl.get("cover_url"))
        result_templates.append(tpl)

    return {
        **results,
        "templates": result_templates
    }


@router.get("/my/templates")
async def get_my_templates(
        request: Request,
        status: Optional[TemplateStatusType] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    results = service.get_my_templates(
        user_id=current_user.id,
        status=status,
        page=page,
        page_size=page_size
    )

    result_templates = []
    for tpl in results["templates"]:
        tpl["cover_url"] = parse_cover_url(request, tpl.get("cover_url"))
        result_templates.append(tpl)

    return {
        **results,
        "templates": result_templates
    }


@router.post("/{template_id}/clone")
async def clone_template(
        request: Request,
        template_id: uuid.UUID,
        new_name: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    cloned = service.clone_template(template_id, current_user.id, new_name)

    return {"template": cloned}


@router.post("/{template_id}/download")
async def download_template(
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    template = service.download_template(template_id, current_user.id)

    return {"template": template}


@router.post("/standalone/page")
async def create_standalone_page(
        request: Request,
        # Đặt File parameter trước Form parameters
        thumbnail_file: Optional[UploadFile] = File(None, description="Thumbnail image", media_type="image/*"),
        page_data: str = Form(..., description="Page data as JSON string"),
        page_scope: Optional[PageScopeType] = Form(PageScopeType.USER, description="Page scope"),
        page_type: Optional[PageType] = Form(PageType.CONTENT, description="Page Type"),
        page_category: Optional[PageCategoryType] = Form(None, description="Page Category"),
        page_section: Optional[PageSectionType] = Form(None, description="Page Section"),
        page_name: Optional[str] = Form(None, description="Page Name"),
        page_description: Optional[str] = Form(None, description="Page Description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    from app.utils.pptx_utils import normalize_element_positions

    try:
        page_json = json.loads(page_data)
        thumbnail_url = None
        if thumbnail_file:
            thumbnail_url = await handle_thumbnail_upload(thumbnail_file)

        parsed_tags = None
        if tags:
            parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Get elements and normalize if source dimensions are provided
        elements = page_json.get("elements", [])
        source_width = page_json.get("source_width") or page_json.get("width")
        source_height = page_json.get("source_height") or page_json.get("height")

        if source_width and source_height:
            elements = normalize_element_positions(elements, source_width, source_height)

        page_info = {
            "page_name": page_name,
            "page_description": page_description,
            "page_type": page_type,
            "page_category": page_category,
            "page_section": page_section,
            "page_scope": page_scope,
            "page_data": elements,
            # "preview_data": page_json.get("preview_data"),
            "thumbnail_url": thumbnail_url,
            "tags": parsed_tags,
            # "animation_count": page_json.get("animation_count", 0),
            # "element_count": page_json.get("element_count", 0),
            # "text_filled_count": page_json.get("text_filled_count", 0),
            "is_active": True
        }

        service = TemplateService(db)
        page = service.create_standalone_page(page_info, current_user.id)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "page": {
                    "id": str(page.id),
                    "page_name": page.page_name,
                    "page_description": page.page_description,
                    "page_type": page.page_type if page.page_type else None,
                    "page_category": page.page_category if page.page_category else None,
                    "page_section": page.page_section if page.page_section else None,
                    "page_scope": page.page_scope,
                    "thumbnail_url": parse_cover_url(request, page.thumbnail_url),
                    "tags": page.tags,
                    "is_active": page.is_active,
                    "created_at": page.created_at.isoformat() if page.created_at else None
                },
                "message": "Standalone page created successfully"
            }
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in page_data")
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error creating page: {str(e)}")


@router.get("/standalone/pages")
async def list_standalone_pages(
        request: Request,
        page_scope: Optional[PageScopeType] = None,
        page_category: Optional[PageCategoryType] = None,
        page_section: Optional[PageSectionType] = None,
        tags: Optional[str] = None,
        active_only: bool = True,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        order_by: str = Query(default="asc"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    filter_tags = None
    if tags:
        filter_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    results = service.get_standalone_pages(
        page_scope=page_scope,
        page_category=page_category,
        page_section=page_section,
        tags=filter_tags,
        active_only=active_only,
        page=page,
        limit=limit,
        order_by=order_by,
        user_id=current_user.id
    )

    return {
        "success": True,
        **results,
        "pages": [
            {
                **page.to_dict_summary(),
                "thumbnail_url": parse_cover_url(request, page.thumbnail_url)
            }
            for page in results['pages']
        ]
    }


@router.get("/standalone/page/{page_id}")
async def get_standalone_page(
        request: Request,
        page_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    page = service.get_standalone_page(page_id, current_user.id)

    if page['page_scope'] == PageScopeType.SYSTEM:
        service.increment_page_usage(page_id)

    pptx_property = {
        k: v for k, v in page.items()
        if k not in ["thumbnail_url", "page_data", "text_filled_count", "element_count", "animation_count"]
    }

    data = {
        **pptx_property,
        "thumbnail_url": parse_cover_url(request, page.get("thumbnail_url")),
        "pptxProperty": encode_response_data({
            "id": page.get("id"),
            "elements": page.get("page_data"),
            "background": {
                "type": "solid",
                "color": "#ffffff"
            },
            "type": "content"
        })
    }

    return data


@router.put("/standalone/page/{page_id}")
async def update_standalone_page(
        page_id: uuid.UUID,
        request: TemplatePageUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    page = service.pages.update_standalone_page(page_id, current_user.id, **update_data)

    return {"page": page}


@router.delete("/standalone/page/{page_id}")
async def delete_standalone_page(
        page_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    success = service.pages.delete_standalone_page(page_id, current_user.id)

    return {"success": success}


@router.post("/{template_id}/submit")
async def submit_for_approval(
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    template = service.submit_for_approval(template_id, current_user.id)

    return {"template": template}


@router.post("/{template_id}/approve")
async def approve_template(
        template_id: uuid.UUID,
        is_featured: bool = False,
        db: Session = Depends(get_db),
        current_admin: User = Depends(get_current_user)
):
    service = TemplateService(db)
    template = service.approve_template(template_id, current_admin.id, is_featured)

    return {"template": template}


@router.post("/{template_id}/reject")
async def reject_template(
        template_id: uuid.UUID,
        rejection_reason: str,
        db: Session = Depends(get_db),
        current_admin: User = Depends(get_current_user)
):
    service = TemplateService(db)
    template = service.reject_template(template_id, current_admin.id, rejection_reason)

    return {"template": template}


@router.get("/admin/pending")
async def get_pending_templates(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db),
        current_admin: User = Depends(get_current_user)
):
    service = TemplateService(db)
    result = service.get_pending_templates(page, page_size)

    return result


@router.post("/{template_id}/like")
async def like_template(
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    is_liked = service.like_template(template_id, current_user.id)

    return {"liked": is_liked}


@router.post("/{template_id}/favorite")
async def add_to_favorites(
        template_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    is_favorited = service.add_to_favorites(template_id, current_user.id)

    return {"favorited": is_favorited}


@router.get("/my/favorites")
async def get_user_favorites(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    results = service.get_user_favorites(current_user.id, page, page_size)

    if results:
        return {
            "success": True,
            **results,
            "templates": [
                {
                    **result.to_dict(),
                    # **TemplateListResponse.model_dump(result).dict(),
                    "cover_url": parse_cover_url(request, result.cover_url)
                }
                for result in results["templates"]
            ]
        }

    return results


@router.post("/{template_id}/reviews")
async def create_review(
        template_id: uuid.UUID,
        request: TemplateReviewRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    review = service.create_review(
        template_id=template_id,
        user_id=current_user.id,
        rating=request.rating,
        review_text=request.review_text
    )

    return {"review": review}


@router.put("/reviews/{review_id}")
async def update_review(
        review_id: uuid.UUID,
        request: TemplateReviewRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    review = service.pages.update_review(
        review_id=review_id,
        user_id=current_user.id,
        rating=request.rating,
        review_text=request.review_text
    )

    return {"review": review}


@router.get("/{template_id}/reviews")
async def get_template_reviews(
        template_id: uuid.UUID,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db)
):
    service = TemplateService(db)
    result = service.get_template_reviews(template_id, page, page_size)

    return result


@router.post("/collections")
async def create_collection(
        request: TemplateCollectionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    collection = service.create_collection(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        is_public=request.is_public
    )

    return {"collection": collection}


@router.post("/collections/{collection_id}/templates/{template_id}")
async def add_template_to_collection(
        collection_id: uuid.UUID,
        template_id: uuid.UUID,
        order_index: int = 0,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    item = service.add_template_to_collection(
        collection_id=collection_id,
        template_id=template_id,
        user_id=current_user.id,
        order_index=order_index
    )

    return {"item": item}


@router.get("/collections/my")
async def get_user_collections(
        include_public: bool = True,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    collections = service.get_user_collections(current_user.id, include_public)

    return {"collections": collections}


@router.get("/{template_id}/analytics")
async def get_template_analytics(
        template_id: uuid.UUID,
        days: int = Query(30, ge=1, le=365),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)
    analytics = service.get_template_analytics(template_id, current_user.id, days)

    return analytics


@router.post("/{template_id}/report")
async def report_template(
        template_id: uuid.UUID,
        request: TemplateReportRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = TemplateService(db)

    report = service.report_template(
        template_id=template_id,
        user_id=current_user.id,
        reason=request.reason,
        description=request.description
    )

    return {"report": report}
