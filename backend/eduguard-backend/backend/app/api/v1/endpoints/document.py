from typing import Optional
import os
import httpx

from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from app.core.config import settings

router = APIRouter()


@router.post("/extract-content")
async def extract_document_content(
    document: UploadFile = File(...),
    extract_tables_as_images: Optional[bool] = Form(False),
    image_resolution_scale: Optional[int] = Form(1)
):

    file_extension = os.path.splitext(document.filename)[1].lower()
    if file_extension not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types are: {', '.join(settings.ALLOWED_FILE_TYPES.keys())}"
        )

    content_type = settings.ALLOWED_FILE_TYPES[file_extension]

    try:
        files = {'document': (document.filename, await document.read(), content_type)}
        data = {
            'extract_tables_as_images': str(extract_tables_as_images).lower(),
            'image_resolution_scale': str(image_resolution_scale)
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.EXTRACT_DOC_API_URL,
                headers={'accept': 'application/json'},
                files=files,
                data=data,
                timeout=120.0
            )
            response.raise_for_status()

        return response.json()

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=500, detail=f"An error occurred while requesting the API"
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"API responded with an error: {exc.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred")
