import os
import io
import base64
import asyncio
import logging
from typing import List, AsyncGenerator

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
# vertexai is heavy and only needed for AI cover images: imported lazily below


from app.services.ai.base import BaseAIService
from app.core.pptagent.schemas import ImageGenerationRequest

logger = logging.getLogger(__name__)


class ImageGenerationService(BaseAIService):
    def __init__(self):
        super().__init__()
        self.model_name = 'imagen-4.0-fast-generate-preview-06-06'
        self._setup_credentials()

    def _setup_credentials(self):
        credentials_path = os.path.join(os.getcwd(), 'app/core/helpers/credentials-dev.json')
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

    async def generate_images(self, img_req: ImageGenerationRequest) -> List[str]:
        try:
            from vertexai.preview.vision_models import ImageGenerationModel
            generation_model = ImageGenerationModel.from_pretrained(self.model_name)

            images = generation_model.generate_images(
                prompt=img_req.prompt,
                number_of_images=img_req.number_of_images,
                aspect_ratio=img_req.aspect_ratio,
                negative_prompt=img_req.negative_prompt,
                person_generation=img_req.person_generation,
                safety_filter_level=img_req.safety_filter_level,
                add_watermark=img_req.add_watermark,
            )

            return self._convert_images_to_base64(images)

        except Exception as e:
            logger.error(f"Image generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

    async def generate_images_stream(self, img_req: ImageGenerationRequest) -> StreamingResponse:
        try:
            from vertexai.preview.vision_models import ImageGenerationModel
            generation_model = ImageGenerationModel.from_pretrained(self.model_name)

            images = generation_model.generate_images(
                prompt=img_req.prompt,
                number_of_images=2,
                aspect_ratio="1:1",
                negative_prompt="",
                person_generation="allow_all",
                safety_filter_level="block_few",
                add_watermark=True,
            )

            async def image_stream() -> AsyncGenerator[str, None]:
                for image in images:
                    base64_image = self._convert_single_image_to_base64(image)
                    yield f"data:image/png;base64,{base64_image}"
                    await asyncio.sleep(0.1)

            return StreamingResponse(image_stream(), media_type="text/plain")

        except Exception as e:
            logger.error(f"Image generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

    def _convert_images_to_base64(self, images) -> List[str]:
        base64_images = []
        for image in images:
            base64_image = self._convert_single_image_to_base64(image)
            base64_images.append(f"data:image/png;base64,{base64_image}")
        return base64_images

    def _convert_single_image_to_base64(self, image) -> str:
        img_buffer = io.BytesIO()
        image._pil_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return base64.b64encode(img_buffer.read()).decode('utf-8')

    async def generate_image_variations(self, base_image: str, num_variations: int = 3) -> List[str]:
        pass

    async def upscale_image(self, image_data: str, scale_factor: int = 2) -> str:
        pass
