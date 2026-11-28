import asyncio
import logging

from app.core.config import settings
from app.core.pptagent.slide_generator import AIPPTGenerator
from app.core.pptagent.types import OperateType
from app.services.ai.base import BaseAIService
from app.services.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ContentService(BaseAIService):

    def __init__(self):
        super().__init__()
        self.agent = AIPPTGenerator(api_key=settings.GEMINI_API_KEY)

    async def generate_presentation_title(self, outline: str, language: str, user_id: int) -> str:
        try:
            # PromptBuilder.validate_prompt_parameters(OperateType.GENERATE_TITLE_PRESENTATION.value,
            #                                          outline=outline,
            #                                          language=language
            #                                          )

            system_prompt = PromptBuilder.get_system_prompt(OperateType.GENERATE_TITLE_PRESENTATION.value)
            prompt = PromptBuilder.build_title_presentation_prompt(outline=outline, language=language)

            result = await self.agent.generate_content(
                prompt=prompt,
                model='gemini-2.5-flash',
                include_thoughts=False,
                system_instruction=system_prompt,
                token_callback=self.token_collector
            )

            collected_usage = self.token_collector.get_token_usage()
            if collected_usage:
                asyncio.create_task(self._track_token_usage(
                    user_id=user_id,
                    operation_type=OperateType.GENERATE_TITLE_PRESENTATION,
                    token_usage=collected_usage,
                    operation_data={"operation": "title_generation", "outline_length": len(outline)}
                ))

            title = result.content.strip().strip('"\'')

            return title if title else "Untitled"

        except Exception as e:
            logger.error(f"Error generating presentation title: {e}", exc_info=True)
            return "Untitled"

    async def improve_content(self, model: str, user_id: int, extracted_text: str, improve_req) -> str:

        try:
            # PromptBuilder.validate_prompt_parameters(OperateType.IMPROVE_CONTENT.value,
            #                                          style=improve_req.style,
            #                                          tone=improve_req.tone,
            #                                          audience=improve_req.audience,
            #                                          topic=improve_req.topic,
            #                                          language=improve_req.language
            #                                          )

            prompt = PromptBuilder.build_content_improvement_prompt(improve_req=improve_req,
                                                                    extracted_text=extracted_text)

            result = await self.agent.generate_content(
                prompt=prompt,
                model=model,
                include_thoughts=False,
                system_instruction=None,
                token_callback=self.token_collector
            )

            collected_usage = self.token_collector.get_token_usage()
            if collected_usage:
                asyncio.create_task(self._track_token_usage(
                    user_id=user_id,
                    operation_type=OperateType.IMPROVE_CONTENT.value,
                    token_usage=collected_usage,
                    operation_data=improve_req.model_dump()
                ))

            return result.content

        except Exception as e:
            logger.error(f"Error in improve content: {e}", exc_info=True)
            raise

    async def enhance_text(self, text: str, style: str, user_id: int) -> str:

        prompt = f"Enhance the following text in {style} style: {text}"

        result = await self.agent.generate_content(
            prompt=prompt,
            model='gemini-2.5-flash',
            token_callback=self.token_collector
        )

        collected_usage = self.token_collector.get_token_usage()
        if collected_usage:
            asyncio.create_task(self._track_token_usage(
                user_id=user_id,
                operation_type=OperateType.CONTENT_ENRICHMENT.value,
                token_usage=collected_usage,
                operation_data={"style": style, "original_length": len(text)}
            ))

        return result.content
