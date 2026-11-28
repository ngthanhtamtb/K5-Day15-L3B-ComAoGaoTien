import os
import re
import json
import traceback
import uuid
import base64
import hashlib
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any, List, Union
from uuid import UUID
import asyncio
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.pptagent.schemas import ImageGenerationRequest
from app.core.pptagent.slide_generator import AIPPTGenerator
from app.core.pptagent.slide_processor import SlideProcessor
from app.core.pptagent.types import OperateType
from app.models.presentation import Presentation, PresentationPage
from app.services.ai.base import BaseAIService
from app.services.ai.prompt_builder import PromptBuilder
from app.services.ai.images import ImageGenerationService
from app.services.presentations import PresentationCoreService
from app.services.templates import TemplateService

logger = logging.getLogger(__name__)


class SlideGenerationService(BaseAIService):
    def __init__(self, db: Session, image_dir: str = "data/images/presentations"):
        super().__init__()
        self.db = db
        self.agent = AIPPTGenerator(api_key=settings.GEMINI_API_KEY)
        self.slide_processor = SlideProcessor()
        self.presentation_service = PresentationCoreService(db)
        self.images = ImageGenerationService()
        self.img_pool = []
        self.image_dir = image_dir

    async def generate_slides_stream(self, user_id: int, template_id: str, outline: str,
                                     document: str, language: str, topic: str, image_urls: List[str],
                                     slide_count: int, presentation_id: Optional[str] = None,
                                     remove_numbering: bool = True,
                                     save_to_presentation: bool = True,
                                     presentation_title: Optional[str] = None,
                                     description: Optional[str] = None,
                                     **kwargs) -> AsyncGenerator[Dict[str, Any], None]:

        template_slides = self._load_template(template_id)
        if image_urls:
            self.img_pool = self._create_image_pool(image_urls)

        presentation = None
        if save_to_presentation:
            presentation = await self._setup_presentation(
                user_id, template_id, presentation_id, presentation_title, description
            )
            presentation_id = str(presentation.id)

            await self._generate_cover_if_needed(presentation, topic, language, user_id, presentation_title)

        try:
            async for slide in self._generate_slides_internal(
                    outline, document, language, topic, slide_count, remove_numbering,
                    template_slides, presentation_id if save_to_presentation else None, user_id
            ):
                yield slide

            if save_to_presentation and presentation:
                await self._finalize_presentation(presentation, topic, language)

            await self._track_usage(user_id, template_id, slide_count, language, topic, presentation_id)

        except Exception as e:
            logger.error(f"Error during slide generation: {e}")
            yield self.slide_processor._create_error_slide(f"Could not generate slides: {str(e)}")

    async def _generate_cover_if_needed(self, presentation: Presentation, topic: str,
                                        language: str, user_id: int, presentation_title: str):
        try:
            if presentation.cover_url:
                logger.info(f"Presentation {presentation.id} already has cover image")
                return

            logger.info(f"Generating cover image for presentation {presentation.id}")

            cover_prompt = self._build_cover_prompt(topic, language, presentation_title)

            cover_url = await self._generate_and_save_cover(cover_prompt, user_id)

            if cover_url:
                presentation.cover_url = cover_url
                self.db.commit()
                logger.info(f"Generated and saved cover image for presentation {presentation.id}: {cover_url}")

        except Exception as e:
            logger.error(f"Error generating cover image for presentation {presentation.id}: {e}")
            pass

    def _build_cover_prompt(self, topic: str, presentation_title: str, language: str = 'japanese') -> str:
        language_styles = {
            'vietnamese': 'Vietnamese style, elegant',
            'english': 'professional, modern',
            'chinese': 'Chinese aesthetic, sophisticated',
            'japanese': 'Japanese minimalist, clean',
            'korean': 'Korean modern, sleek'
        }

        style = language_styles.get(language.lower(), 'professional, modern, Japanese minimalist, clean')

        prompt = f"""Create a professional presentation cover image for the topic: "{presentation_title}". 
        The image should be {style}, suitable for business presentations, with clean composition, 
        abstract or symbolic elements related to {presentation_title}, no text or words, 
        corporate color scheme, high quality, suitable for presentation thumbnail"""

        return prompt[:1000]

    async def _generate_and_save_cover(self, prompt: str, user_id: int) -> Optional[str]:
        try:
            img_req = ImageGenerationRequest(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="16:9",
                negative_prompt="text, words, letters, low quality, blurry, watermark",
                person_generation="allow_all",
                safety_filter_level="block_few",
                add_watermark=False
            )

            base64_images = await self.images.generate_images(img_req)

            if not base64_images:
                logger.warning("No images generated for cover")
                return None

            b64_str = base64_images[0]
            if b64_str.startswith("data:image"):
                b64_str = b64_str.split(",", 1)[1]

            img_bytes = base64.b64decode(b64_str)
            file_hash = hashlib.sha256(str(user_id).encode('utf-8') + img_bytes).hexdigest()
            filename = f"cover_{file_hash}.png"
            file_path = os.path.join(self.image_dir, filename)

            with open(file_path, "wb") as f:
                f.write(img_bytes)

            cover_url = f"/images/presentations/{filename}"

            logger.info(f"Saved cover image to {file_path}, URL: {cover_url}")
            return cover_url

        except Exception as e:
            logger.error(f"Error generating and saving cover image: {e}")
            return None

    async def _setup_presentation(self, user_id: int, template_id: str,
                                  presentation_id: Optional[str], title: Optional[str],
                                  description: Optional[str]) -> Presentation:
        if presentation_id:
            presentation = await self._get_or_create_presentation(
                user_id, template_id, presentation_id, title, description
            )

            existing_count = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation.id
            ).count()

            if existing_count > 0:
                if not self.presentation_service.permissions.can_edit(presentation, user_id):
                    raise HTTPException(status_code=403, detail="Not authorized to edit presentation")
                await self._clear_slides(str(presentation.id))

        else:
            presentation = await self._create_new_presentation(user_id, template_id, title, description)

        return presentation

    async def _get_or_create_presentation(self, user_id: int, template_id: str,
                                          presentation_id: str, title: Optional[str],
                                          description: Optional[str]) -> Presentation:
        try:
            presentation = self.db.query(Presentation).filter(
                Presentation.id == UUID(presentation_id)
            ).first()

            if presentation:
                if presentation.owner_id != user_id:
                    if not self.presentation_service.permissions.can_view(presentation, user_id):
                        raise HTTPException(status_code=403, detail="Not authorized to access presentation")
                return presentation

            return await self._create_presentation_with_id(
                user_id, template_id, presentation_id, title, description
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting/creating presentation: {e}")
            raise HTTPException(status_code=500, detail=f"Error handling presentation: {str(e)}")

    async def _create_presentation_with_id(self, user_id: int, template_id: str,
                                           presentation_id: str, title: Optional[str],
                                           description: Optional[str]) -> Presentation:
        try:
            presentation = Presentation(
                id=UUID(presentation_id),
                title=title or "AI Generated Presentation",
                description=description or "AI-generated presentation",
                owner_id=user_id,
                template_id=template_id,
                status="private",
                page_count=0,
                cover_url=None
            )

            self.db.add(presentation)
            self.db.commit()
            self.db.refresh(presentation)

            logger.info(f"Created presentation {presentation_id} for user {user_id}")
            return presentation

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating presentation with ID: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create presentation: {str(e)}")

    async def _create_new_presentation(self, user_id: int, template_id: str,
                                       title: Optional[str], description: Optional[str]) -> Presentation:
        try:
            presentation = Presentation(
                title=title or "AI Generated Presentation",
                description=description or "AI-generated presentation",
                owner_id=user_id,
                template_id=template_id,
                status="private",
                page_count=0,
                cover_url=None
            )

            self.db.add(presentation)
            self.db.commit()
            self.db.refresh(presentation)

            logger.info(f"Created new presentation {presentation.id} for user {user_id}")
            return presentation

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating presentation: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create presentation: {str(e)}")

    async def _generate_slides_internal(self, outline: str, document: str, language: str,
                                        topic: str, slide_count: int, remove_numbering: bool,
                                        template_slides: List[Dict], presentation_id: Optional[str],
                                        user_id: int) -> AsyncGenerator[Dict[str, Any], None]:
        prompt = PromptBuilder.build_slide_generation_prompt(
            outline, document, language, topic, slide_count, remove_numbering
        )

        buffer = ""
        slide_idx = 0

        async for chunk_content in self.agent.generate_content_stream(
                system_instruction=None,
                prompt=prompt,
                model='gemini-2.5-flash',
                token_callback=self.token_collector
        ):
            if not chunk_content.content:
                continue

            buffer += chunk_content.content
            await asyncio.sleep(0.01)

            async for slide_data_raw, new_buffer in self.slide_processor._process_buffer_for_slides(buffer):
                if slide_data_raw:
                    mapped_slide = await self._process_slide(slide_data_raw, template_slides)
                    if mapped_slide:
                        slide_idx += 1

                        if presentation_id:
                            await self._save_slide(presentation_id, mapped_slide, slide_data_raw, slide_idx)

                        yield mapped_slide

                buffer = new_buffer

        async for remaining_slide in self._process_remaining_buffer(
                buffer, template_slides, slide_idx, presentation_id
        ):
            if remaining_slide:
                slide_idx += 1
                yield remaining_slide

    async def _save_slide(self, presentation_id: str, mapped_slide: Dict,
                          slide_data_raw: Dict, page_order: int):
        try:
            presentation = self.db.query(Presentation).filter(
                Presentation.id == UUID(presentation_id)
            ).first()

            if not presentation:
                logger.error(f"Presentation {presentation_id} not found when saving slide {page_order}")
                return

            page_data = slide_data_raw.get('data', {})
            page_name = page_data.get('title', f"Slide {page_order}")
            page_type = slide_data_raw.get('type', 'content')
            background = mapped_slide.get('background', {
                "type": "solid",
                "color": "#ffffff"
            })

            existing_page = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == UUID(presentation_id),
                PresentationPage.page_order == page_order
            ).first()

            if existing_page:
                existing_page.page_name = page_name
                existing_page.page_type = page_type
                existing_page.background = background
                existing_page.page_data = mapped_slide.get('elements', [])
                existing_page.speaker_notes = page_data.get('speaker_notes', '')
                existing_page.element_count = len(mapped_slide.get('elements', []))
                existing_page.updated_at = datetime.now()
            else:
                page = PresentationPage(
                    presentation_id=UUID(presentation_id),
                    template_page_id=mapped_slide.get('template_page_id'),
                    page_order=page_order,
                    page_name=page_name,
                    page_type=page_type,
                    background=background,
                    page_data=mapped_slide.get('elements', []),
                    speaker_notes=page_data.get('speaker_notes', ''),
                    element_count=len(mapped_slide.get('elements', []))
                )
                self.db.add(page)

            self.db.commit()

        except Exception as e:
            logger.error(f"Error saving slide {page_order}: {e}")
            self.db.rollback()

    async def _clear_slides(self, presentation_id: str):
        try:
            deleted_count = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == UUID(presentation_id)
            ).delete()

            presentation = self.db.query(Presentation).filter(
                Presentation.id == UUID(presentation_id)
            ).first()

            if presentation:
                presentation.page_count = 0

            self.db.commit()
            logger.info(f"Cleared {deleted_count} slides from presentation {presentation_id}")

        except Exception as e:
            logger.error(f"Error clearing slides: {e}")
            self.db.rollback()
            raise

    async def _finalize_presentation(self, presentation: Presentation, topic: str, language: str):
        try:
            total_slides = self.db.query(PresentationPage).filter(
                PresentationPage.presentation_id == presentation.id
            ).count()

            presentation.page_count = total_slides

            # if not presentation.theme_data:
            #     presentation.theme_data = {}
            # presentation.theme_data.update({})

            if not presentation.ext_info:
                presentation.ext_info = {}

            presentation.ext_info.update({
                "last_generation": {
                    "topic": topic,
                    "language": language,
                    "slide_count": total_slides,
                    "generated_at": datetime.now().isoformat()
                }
            })

            self.db.commit()

            try:
                self.presentation_service.activity.log(
                    presentation.id, presentation.owner_id, "slides_generated",
                    {"slide_count": total_slides, "topic": topic}
                )
            except Exception as e:
                logger.warning(f"Could not log activity: {e}")

        except Exception as e:
            logger.error(f"Error finalizing presentation: {e}")
            self.db.rollback()

    def _load_template(self, template_id: str) -> List[Dict]:
        try:
            service = TemplateService(self.db)
            template = service.get_template(template_id)

            if not template:
                raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

            slides = []
            if hasattr(template, 'pages') and template.pages:
                active_pages = [page for page in template.pages if page.is_active]
                sorted_pages = sorted(active_pages, key=lambda p: p.page_order or 0)

                for page in sorted_pages:
                    slides.append({
                        "id": str(page.id),
                        "type": page.page_type,
                        "background": page.background,
                        "elements": page.page_data or []
                    })

            return slides

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid template: {str(e)}")

    def _create_image_pool(self, image_urls: List[str]) -> List[Dict]:
        return [
            {
                "id": self.slide_processor._generate_nanoid(),
                "src": url,
                "width": 1920,
                "height": 1080
            }
            for url in image_urls
        ]

    async def _process_slide(self, slide_data_raw: Dict, template_slides: List[Dict]) -> Optional[Dict]:
        try:
            mapped_slide = await self.slide_processor._map_ai_slide_to_template(
                slide_data_raw, template_slides
            )

            if not mapped_slide:
                logger.warning(f"Could not map slide: {slide_data_raw.get('type')}")
                return self.slide_processor._create_error_slide(
                    f"Could not map slide: {slide_data_raw.get('type')}"
                )

            return mapped_slide

        except Exception as e:
            logger.error(f"Error processing slide: {e}")
            return self.slide_processor._create_error_slide(f"Error processing slide: {str(e)}")

    async def _process_remaining_buffer(self, buffer: str, template_slides: List[Dict],
                                        current_slide_idx: int, presentation_id: Optional[str]):
        if not buffer.strip():
            return

        try:
            json_pattern = r'\{\s*"type"\s*:\s*"[^"]+"\s*,\s*"data"\s*:\s*\{[^}]+\}\s*\}'
            matches = re.finditer(json_pattern, buffer, re.DOTALL)

            slide_count = 0
            for match in matches:
                try:
                    slide_data_raw = json.loads(match.group(0))
                    if self.slide_processor._validate_slide_data(slide_data_raw):
                        mapped_slide = await self._process_slide(slide_data_raw, template_slides)
                        if mapped_slide:
                            slide_count += 1
                            page_order = current_slide_idx + slide_count

                            if presentation_id:
                                await self._save_slide(presentation_id, mapped_slide, slide_data_raw, page_order)

                            yield mapped_slide
                            await asyncio.sleep(0.01)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in buffer: {e}")

        except Exception as e:
            logger.error(f"Error processing remaining buffer: {e}")
            yield self.slide_processor._create_error_slide(f"Error processing final content: {str(e)}")

    async def _track_usage(self, user_id: int, template_id: str, slide_count: int,
                           language: str, topic: str, presentation_id: Optional[str]):
        try:
            usage = self.token_collector.get_token_usage()
            if usage:
                operation_data = {
                    "template_id": template_id,
                    "slide_count": slide_count,
                    "language": language,
                    "topic": topic,
                    "presentation_id": presentation_id
                }
                asyncio.create_task(self._track_token_usage(
                    user_id=user_id,
                    operation_type=OperateType.GENERATE_PRESENTATION,
                    token_usage=usage,
                    operation_data=operation_data
                ))
        except Exception as e:
            logger.warning(f"Could not track usage: {e}")

    async def clear_presentation_slides(self, presentation_id: str, user_id: int):
        try:
            presentation = self.db.query(Presentation).filter(
                Presentation.id == UUID(presentation_id)
            ).first()

            if not presentation:
                raise HTTPException(status_code=404, detail="Presentation not found")

            if not self.presentation_service.permissions.can_edit(presentation, user_id):
                raise HTTPException(status_code=403, detail="Not authorized to edit presentation")

            await self._clear_slides(presentation_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in clear_presentation_slides: {e}")
            raise HTTPException(status_code=500, detail=str(e))
