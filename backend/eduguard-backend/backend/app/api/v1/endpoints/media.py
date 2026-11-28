import os
import uuid
import hashlib
import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Query, status as http_status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.media import MediaAsset
from app.utils.pptx_utils import parse_cover_url

router = APIRouter()


@router.get("/fonts/{font_name}")
async def get_font_file(font_name: str):
    if any(x in font_name for x in ["..", "/", "\\"]):
        raise HTTPException(status_code=400, detail="Invalid font name")

    font_dir = os.path.join(os.getcwd(), "data/fonts")
    font_path = os.path.join(font_dir, font_name)

    return FileResponse(path=font_path, filename=font_name, media_type="font/woff2")


@router.get("/images/{filename}")
async def get_image(filename: str):
    file_extension = Path(filename).suffix.lower()
    if file_extension not in settings.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported formats: {', '.join(settings.SUPPORTED_EXTENSIONS)}"
        )

    file_path = settings.IMAGES_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Path is not a file")

    media_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml'
    }

    media_type = media_type_map.get(file_extension, 'image/jpeg')

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            # "Cache-Control": "public, max-age=3600",
            "Content-Disposition": "inline"
        }
    )


@router.get("/")
async def get_media_assets(
        request: Request,
        file_type: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(MediaAsset).filter(MediaAsset.user_id == current_user.id)

    if file_type:
        query = query.filter(MediaAsset.file_type == file_type)

    assets = query.offset(skip).limit(limit).all()
    data = []
    for asset in assets:
        asset.file_path = parse_cover_url(request, asset.file_path)
        data.append(asset)

    return data


@router.post("/upload")
async def upload_media(
        request: Request,
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    file_type = "image"
    if file.content_type.startswith("video/"):
        file_type = "video"
    elif file.content_type.startswith("audio/"):
        file_type = "audio"
    elif file.content_type in ["application/pdf", "application/msword"]:
        file_type = "document"

    file_path = f"data/uploads/media/{unique_filename}"
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    media_asset = MediaAsset(
        user_id=current_user.id,
        filename=unique_filename,
        original_filename=file.filename,
        file_path=f"/uploads/media/{unique_filename}",
        file_type=file_type,
        mime_type=file.content_type,
        file_size=file.size,
        metadata={"uploaded_via": "api"}
    )

    db.add(media_asset)
    db.commit()
    db.refresh(media_asset)

    return {
        "id": media_asset.id,
        "filename": media_asset.filename,
        "original_filename": media_asset.original_filename,
        "file_type": media_asset.file_type,
        "file_size": media_asset.file_size,
        "url": parse_cover_url(request=request, url=f"/uploads/media/{unique_filename}")
    }


@router.delete("/{asset_id}")
async def delete_media_asset(
        asset_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.user_id == current_user.id
    ).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    try:
        os.remove(asset.file_path)
    except FileNotFoundError:
        pass

    db.delete(asset)
    db.commit()

    return {"message": "Media asset deleted successfully"}


@router.put("/{asset_id}")
async def update_media_asset(
        asset_id: int,
        metadata: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.user_id == current_user.id
    ).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    asset.metadata = {**asset.metadata, **metadata}
    db.commit()
    db.refresh(asset)

    return asset


@router.get("/{asset_id}/info")
async def get_media_info(
        asset_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.user_id == current_user.id
    ).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    return {
        "id": asset.id,
        "filename": asset.filename,
        "original_filename": asset.original_filename,
        "file_type": asset.file_type,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "metadata": asset.metadata,
        "is_ai_generated": asset.is_ai_generated,
        "created_at": asset.created_at,
        "url": f"/uploads/media/{asset.filename}"
    }


@router.post("/bulk-upload")
async def bulk_upload_media(
        files: List[UploadFile] = File(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed")

    uploaded_files = []

    for file in files:
        try:
            if file.size > settings.MAX_FILE_SIZE:
                uploaded_files.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": "File too large"
                })
                continue

            file_extension = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            file_type = "image"
            if file.content_type.startswith("video/"):
                file_type = "video"
            elif file.content_type.startswith("audio/"):
                file_type = "audio"
            elif file.content_type in ["application/pdf", "application/msword"]:
                file_type = "document"

            upload_dir = Path(settings.UPLOAD_DIR) / "media"
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_path = upload_dir / unique_filename
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            media_asset = MediaAsset(
                user_id=current_user.id,
                filename=unique_filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_type=file_type,
                mime_type=file.content_type,
                file_size=file.size,
                metadata={"uploaded_via": "bulk_api"}
            )

            db.add(media_asset)
            db.commit()
            db.refresh(media_asset)

            uploaded_files.append({
                "id": media_asset.id,
                "filename": file.filename,
                "status": "success",
                "url": f"/uploads/media/{unique_filename}"
            })

        except Exception as e:
            uploaded_files.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })

    return {"uploaded_files": uploaded_files}


# @router.get("/stock")
# async def search_stock_images(
#         query: str = Query(...),
#         limit: int = Query(20, ge=1, le=50),
#         current_user: User = Depends(get_current_user)
# ):
#     return {
#         "query": query,
#         "results": [
#             {
#                 "id": f"stock_{i}",
#                 "url": f"/placeholder.svg?height=400&width=600",
#                 "thumbnail": f"/placeholder.svg?height=200&width=300",
#                 "title": f"Stock image {i} for {query}",
#                 "source": "placeholder"
#             }
#             for i in range(1, min(limit + 1, 21))
#         ]
#     }
#
#
# @router.post("/generate")
# async def generate_media_with_ai(
#         prompt: str,
#         media_type: str = "image",
#         current_user: User = Depends(get_current_user),
#         db: Session = Depends(get_db)
# ):
#
#     unique_filename = f"ai_generated_{uuid.uuid4()}.png"
#
#     media_asset = MediaAsset(
#         user_id=current_user.id,
#         filename=unique_filename,
#         original_filename=f"AI Generated - {prompt[:50]}.png",
#         file_path=f"/uploads/media/{unique_filename}",
#         file_type=media_type,
#         mime_type="image/png",
#         file_size=1024,
#         is_ai_generated=True,
#         generation_prompt=prompt,
#         metadata={"generation_type": media_type, "prompt": prompt}
#     )
#
#     db.add(media_asset)
#     db.commit()
#     db.refresh(media_asset)
#
#     return {
#         "id": media_asset.id,
#         "status": "generated",
#         "url": f"/placeholder.svg?height=400&width=600",
#         "prompt": prompt
#     }
