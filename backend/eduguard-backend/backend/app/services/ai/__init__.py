from sqlalchemy.orm import Session

from app.services.ai.outline import OutlineService
from app.services.ai.content import ContentService
from app.services.ai.slides import SlideGenerationService
from app.services.ai.slide_enrichment import SlideEnrichmentService, SlideEnrichmentDataService
from app.services.ai.images import ImageGenerationService
from app.services.ai.analytics import AIAnalyticsService


class AIPPTService:

    def __init__(self, db: Session):
        self.outline = OutlineService()
        self.content = ContentService()
        self.slides = SlideGenerationService(db)
        self.images = ImageGenerationService()
        self.analytics = AIAnalyticsService()

    async def generate_pptx_outline(self, *args, **kwargs):
        return await self.outline.generate_outline(*args, **kwargs)

    async def generate_pptx_outline_stream(self, *args, **kwargs):
        async for chunk in self.outline.generate_outline_stream(*args, **kwargs):
            yield chunk

    async def improve_content(self, *args, **kwargs):
        return await self.content.improve_content(*args, **kwargs)

    async def enhance_text(self, *args, **kwargs):
        return await self.content.enhance_text(*args, **kwargs)

    async def generate_slides_stream(self, *args, **kwargs):
        async for slide in self.slides.generate_slides_stream(*args, **kwargs):
            yield slide

    async def generate_image(self, *args, **kwargs):
        return await self.images.generate_images(*args, **kwargs)

    async def get_user_token_usage(self, *args, **kwargs):
        return await self.analytics.get_user_token_usage(*args, **kwargs)

    async def get_usage_summary(self, *args, **kwargs):
        return await self.analytics.get_usage_summary(*args, **kwargs)

    def _extract_json_from_response(self, content: str):
        return self.outline._extract_json_from_response(content)

    async def _track_token_usage_async(self, *args, **kwargs):
        return await self.outline._track_token_usage(*args, **kwargs)