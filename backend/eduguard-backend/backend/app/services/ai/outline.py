import asyncio
import logging

from app.core.config import settings
from app.core.pptagent.slide_generator import AIPPTGenerator
from app.core.pptagent.schemas import OutlineGenerateRequest
from app.core.pptagent.types import OperateType
from app.services.ai.base import BaseAIService
from app.services.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class OutlineService(BaseAIService):

    def __init__(self):
        super().__init__()
        self.agent = AIPPTGenerator(api_key=settings.GEMINI_API_KEY)

    async def generate_outline(self, outline_req: OutlineGenerateRequest, user_id: int,
                               system_prompt: str = None, prompt: str =  None) -> str:

        try:
            # PromptBuilder.validate_prompt_parameters(OperateType.GENERATE_OUTLINE.value,
            #                                          content=outline_req.content,
            #                                          audience=outline_req.audience,
            #                                          style=outline_req.style,
            #                                          tone=outline_req.tone,
            #                                          language=outline_req.language
            #                                          )

            system_prompt = PromptBuilder.get_system_prompt(OperateType.GENERATE_OUTLINE.value) if system_prompt is None else system_prompt
            prompt = PromptBuilder.build_outline_generation_prompt(outline_req) if prompt is None else prompt

            result = await self.agent.generate_content(
                system_instruction=system_prompt,
                prompt=prompt,
                include_thoughts=outline_req.include_thoughts,
                model=outline_req.model,
                token_callback=self.token_collector
            )

            collected_usage = self.token_collector.get_token_usage()
            if collected_usage:
                asyncio.create_task(self._track_token_usage(
                    user_id=user_id,
                    operation_type=OperateType.GENERATE_OUTLINE.value,
                    token_usage=collected_usage,
                    operation_data=outline_req.model_dump()
                ))

            return result

        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            raise

    async def generate_outline_stream(self,outline_req: OutlineGenerateRequest, user_id: int,
                                      system_prompt: str = None, prompt: str =  None):

        try:
            # PromptBuilder.validate_prompt_parameters(OperateType.GENERATE_OUTLINE.value,
            #                                          content=outline_req.content,
            #                                          audience=outline_req.audience,
            #                                          style=outline_req.style,
            #                                          tone=outline_req.tone,
            #                                          language=outline_req.language
            #                                          )

            system_prompt = PromptBuilder.get_system_prompt(OperateType.GENERATE_OUTLINE.value) if system_prompt is None else system_prompt
            prompt = PromptBuilder.build_outline_generation_prompt(outline_req) if prompt is None else prompt

            async for chunk in self.agent.generate_content_stream(
                    system_instruction=system_prompt,
                    prompt=prompt,
                    include_thoughts=outline_req.include_thoughts,
                    model=outline_req.model,
                    token_callback=self.token_collector
            ):
                yield chunk.content
                await asyncio.sleep(0.05)

            collected_usage = self.token_collector.get_token_usage()
            if collected_usage:
                asyncio.create_task(self._track_token_usage(
                    user_id=user_id,
                    operation_type=OperateType.GENERATE_OUTLINE.value,
                    token_usage=collected_usage,
                    operation_data=outline_req.model_dump()
                ))
            else:
                logger.warning("No token usage collected despite successful generation")

        except Exception as e:
            logger.error(f"Error in stream outline: {e}")
            raise
