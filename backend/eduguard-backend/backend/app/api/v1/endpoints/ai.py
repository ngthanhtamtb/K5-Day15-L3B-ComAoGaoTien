import os
import json
import traceback
import asyncio
import datetime
import base64
import hashlib
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.response import success_response, error_response, ResponseCode
from app.core.exceptions import AIServiceException
from app.models.user import User
from app.services.ai import AIPPTService, SlideEnrichmentService, SlideEnrichmentDataService
from app.core.pptagent.schemas import (
    OutlineGenerateRequest, OutlineResponse, AIGeneratePresentationRequest, SlideImprovementContentRequest,
    SlideEnrichmentRequest, ImageGenerationResponse, ImageGenerationRequest
)
from app.schemas.ai import (
    AIImproveContentRequest, AIGenerateImageRequest, AIDocumentProcessRequest, AIGenerationResponse
)
from app.utils.pptx_utils import (
    encode_response_data, inject_text_back_into_html, extract_text_and_prepare_prompt
)
from app.utils.common import generate_numeric_id

router = APIRouter()


@router.get("/data/{template_name}")
async def get_slides(
        template_name: str,
        raw_response: bool = False,
        # current_user: User = Depends(get_current_user)
):
    if any(x in template_name for x in ["..", "/", "\\"]):
        raise HTTPException(400, detail="Invalid template name")

    slides_path = os.path.join(os.getcwd(), "data/templates", template_name)

    if not os.path.isfile(slides_path):
        error = {
            "error": "not_found_or_invalid_file",
            "message": f"'{template_name}' is missing or not a file"
        }
        if raw_response:
            raise HTTPException(404, detail=error)

        raise HTTPException(404, detail=error)

    try:
        with open(slides_path, "r", encoding="utf-8") as f:
            slides_data = json.load(f)
    except Exception as e:
        error = {
            "error": "load_failed",
            "message": f"Error reading template"
        }
        if raw_response:
            raise HTTPException(400, detail=error)

        raise HTTPException(400, detail=error)

    encoded_slides = encode_response_data(slides_data)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "data": {
            "pptInfo": {
                "id": generate_numeric_id(),
                "name": template_name.replace(".json", ""),
                "subject": template_name.replace(".json", ""),
                "fileUrl": None,
                "templateId": generate_numeric_id(),
                "pptxProperty": encoded_slides if not raw_response else slides_data,
                "companyId": 1380,
                "updateTime": now_str,
                "createTime": now_str,
                "extInfo": None,
                "totalPage": 0
            }
        },
        "code": 0,
        "message": "ok"
    }


@router.post("/outline/generate", response_model=OutlineResponse, summary="Generate Presentation Outline")
async def generate_outline(
        outline_req: OutlineGenerateRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        ai_service = AIPPTService(db)

        if outline_req.stream:
            return StreamingResponse(
                ai_service.generate_pptx_outline_stream(
                    outline_req=outline_req,
                    user_id=current_user.id
                ),
                media_type="text/event-stream"
            )
        else:
            outline = await ai_service.generate_pptx_outline(
                outline_req=outline_req,
                user_id=current_user.id
            )
            return OutlineResponse(outline=outline)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIServiceException as e:
        print(f"AI Service Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        print(f"Unexpected error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/generate/slides", response_model=AIGenerationResponse)
async def generate_slides(
        ppt_req: AIGeneratePresentationRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        ai_service = AIPPTService(db)

        async def event_stream():
            try:
                yield json.dumps({"event": "start", "message": "Slide generation started."})
                await asyncio.sleep(0.01)

                idx = 0
                async for slide_data in ai_service.generate_slides_stream(
                        user_id=current_user.id,
                        template_id=ppt_req.template_id,
                        outline=ppt_req.outline,
                        document=ppt_req.document,
                        language=ppt_req.language,
                        style=ppt_req.style,
                        audience=ppt_req.audience,
                        topic=ppt_req.topic,
                        tone=ppt_req.tone,
                        image_urls=ppt_req.image_urls,
                        slide_count=ppt_req.slide_count
                ):
                    yield json.dumps({
                        "event": "slide",
                        "index": idx,
                        "data": encode_response_data(slide_data),
                        "message": f"Slide {idx + 1} generated successfully."
                    })
                    idx += 1

                yield json.dumps({"event": "done", "message": "Slide generation completed."})

            except HTTPException as e:
                yield json.dumps({
                    "event": "error",
                    "status_code": e.status_code,
                    "message": e.detail
                })

            except Exception as e:
                print(f"Lỗi không mong muốn trong stream: {e}")
                yield json.dumps({
                    "event": "error",
                    "status_code": 500,
                    "message": f"Unexpected error: {str(e)}"
                })

        return EventSourceResponse(event_stream())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/presentation", response_model=AIGenerationResponse)
async def generate_presentation(
        ppt_req: AIGeneratePresentationRequest,
        current_user: User = Depends(get_current_user),
        clear_existing: bool = False,
        db: Session = Depends(get_db)
):
    try:
        ai_service = AIPPTService(db)

        if not ppt_req.presentation_id:
            raise HTTPException(status_code=400, detail="presentation_id is required")

        async def element_stream():
            try:
                if ppt_req.title is None:
                    ppt_req.title = await ai_service.content.generate_presentation_title(
                        outline=ppt_req.outline or ppt_req.topic or "",
                        language=ppt_req.language,
                        user_id=current_user.id
                    )

                yield json.dumps({"event": "start", "title": ppt_req.title, "presentation_id": ppt_req.presentation_id,
                                  "message": "Slide generation started."})
                await asyncio.sleep(0.01)

                slide_idx = 0
                async for slide_data in ai_service.generate_slides_stream(
                        user_id=current_user.id,
                        template_id=ppt_req.template_id,
                        presentation_title=ppt_req.title,
                        presentation_id=ppt_req.presentation_id,
                        outline=ppt_req.outline,
                        document=ppt_req.document,
                        language=ppt_req.language,
                        style=ppt_req.style,
                        audience=ppt_req.audience,
                        topic=ppt_req.topic,
                        tone=ppt_req.tone,
                        image_urls=ppt_req.image_urls,
                        slide_count=ppt_req.slide_count
                ):

                    yield json.dumps({
                        "event": "slide_page",
                        "presentation_id": ppt_req.presentation_id,
                        "slide_index": slide_idx,
                        "data": encode_response_data({
                            "id": slide_data.get("id"),
                            "elements": [],
                            "background": slide_data.get("background"),
                            "type": slide_data.get("type")
                        })
                    })

                    elements = slide_data.get("elements", [])
                    for element_idx, element in enumerate(elements):
                        yield json.dumps({
                            "event": "element",
                            "presentation_id": ppt_req.presentation_id,
                            "id": slide_data.get("id"),
                            "slide_index": slide_idx,
                            "element_index": element_idx,
                            "data": encode_response_data(element)
                        })
                        await asyncio.sleep(0.3)

                    await asyncio.sleep(0.3)
                    slide_idx += 1

                yield json.dumps({"event": "done", "presentation_id": ppt_req.presentation_id,
                                  "message": "All elements generated successfully."})

            except HTTPException as e:
                yield json.dumps({
                    "event": "error",
                    "presentation_id": ppt_req.presentation_id,
                    "status_code": e.status_code,
                    "message": e.detail
                })
            except Exception as e:
                yield json.dumps({
                    "event": "error",
                    "presentation_id": ppt_req.presentation_id,
                    "status_code": 500,
                    "message": f"Unexpected error: {str(e)}"
                })

        return EventSourceResponse(element_stream())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content/improve")
async def improve_slide_text(
        improve_req: SlideImprovementContentRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        extracted_text, original_input, is_html = extract_text_and_prepare_prompt(improve_req.text_to_improve)

        ai_service = AIPPTService(db)
        improved_text = await ai_service.improve_content(
            model='gemini-2.5-flash',
            extracted_text=extracted_text,
            improve_req=improve_req,
            user_id=current_user.id
        )

        final_text = inject_text_back_into_html(original_input, improved_text) if is_html else improved_text

        return {
            "page_id": improve_req.page_id,
            "element_id": improve_req.element_id,
            "text": final_text,
            "status": "completed"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Content improvement error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/ppt/enrich-slides/stream", summary="Enrich PPTX slides")
async def stream_slides_data(
        slide_data: Dict[str, Any],
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
) -> EventSourceResponse:

    async def stream_generator():
        try:
            data_service = SlideEnrichmentDataService()
            async for result in data_service.stream_slide_data(slide_data):
                try:
                    event_data = json.loads(result)
                    event_type = event_data.get("event", "data")

                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data)
                    }

                    if event_type == "done":
                        break

                except json.JSONDecodeError:
                    yield {
                        "event": "data",
                        "data": result
                    }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({
                    "event": "error",
                    "message": f"Stream error: {str(e)}",
                    "presentation_id": slide_data.get("presentation_id", "unknown")
                })
            }

    return EventSourceResponse(
        stream_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.post("/generate-images", response_model=ImageGenerationResponse)
async def generate_images(
        img_req: ImageGenerationRequest,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    start_time = datetime.datetime.now()
    try:
        ai_service = AIPPTService(db)
        base64_images = await ai_service.generate_image(img_req)

        IMAGE_DIR = "data/images/aippt"

        base_url = str(request.base_url).rstrip('/')
        image_urls = []

        for b64_str in base64_images:
            if b64_str.startswith("data:image"):
                b64_str = b64_str.split(",", 1)[1]

            img_bytes = base64.b64decode(b64_str)

            file_hash = hashlib.sha256(str(current_user.id).encode('utf-8') + img_bytes).hexdigest()
            filename = f"{file_hash}.png"
            file_path = os.path.join(IMAGE_DIR, filename)

            with open(file_path, "wb") as f:
                f.write(img_bytes)

            relative_url = f"/static/images/aippt/{filename}"
            absolute_url = f"{base_url}{relative_url}"
            image_urls.append(absolute_url)

        generation_time = (datetime.datetime.now() - start_time).total_seconds()

        return ImageGenerationResponse(
            success=True,
            message=f"Successfully generated {len(image_urls)} image(s)",
            images=image_urls,
            generation_time=generation_time,
            timestamp=datetime.datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
