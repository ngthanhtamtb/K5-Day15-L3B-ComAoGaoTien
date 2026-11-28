from typing import Dict, Any, Optional, Callable, AsyncGenerator
from app.core.exceptions import AIServiceException
from app.core.pptagent.llm_client import GeminiAIStudio


class AIPPTGenerator:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = GeminiAIStudio(api_key=api_key, model=model)

    async def generate_content(
            self,
            prompt: str,
            model: str,
            include_thoughts=False,
            system_instruction: Optional[str] = None,
            token_callback: Optional[Callable] = None
    ):
        try:
            result = await self.client.generate_content(
                messages=prompt,
                stream=True,
                include_thinking=include_thoughts,
                callback=token_callback,
                thinking_budget=0
            )
            return result

        except Exception as e:
            raise AIServiceException(f"Failed to generate content: {str(e)}")

    async def generate_content_stream(
            self,
            prompt: str,
            model: str,
            include_thoughts=False,
            system_instruction: Optional[str] = None,
            token_callback: Optional[Callable] = None
    ):
        try:
            async for chunk in self.client.async_generate_content(
                    messages=prompt,
                    include_thinking=include_thoughts,
                    callback=token_callback,
                    thinking_budget=0
            ):
                yield chunk
                # print(chunk.content)
                # if chunk.is_final:
                #     print(f"\n🏁 Final chunk with complete usage: {chunk.usage if chunk.usage else 'N/A'}")

        except Exception as e:
            print(f"Error during content streaming in agent: {e}")
            raise AIServiceException(f"Failed to stream content: {str(e)}")
