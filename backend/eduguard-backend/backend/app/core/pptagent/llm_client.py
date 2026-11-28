import re
import base64
import traceback
import logging
from dataclasses import dataclass, asdict
from typing import Callable, Dict, Any, List, Optional, Union, Literal, AsyncGenerator
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    internal_thinking_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StreamChunk:
    content: str
    is_thinking: bool
    estimated_tokens: int = 0
    chunk_id: int = 0
    usage: Optional[TokenUsage] = None
    is_final: bool = False


@dataclass
class ContentResult:
    prompt: str
    thinking: str
    content: str
    usage: TokenUsage
    chunks: List[StreamChunk]
    content_type: Literal["text", "image", "video"] = "text"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "thinking": self.thinking,
            "content": self.content,
            "usage": self.usage.to_dict(),
            "chunks": [asdict(c) for c in self.chunks],
            "content_type": self.content_type,
            "error": self.error
        }

    def get_token_summary(self) -> str:
        return f"""
Token Usage Summary:
- Prompt tokens: {self.usage.prompt_tokens}
- Completion tokens: {self.usage.completion_tokens}
- Total tokens: {self.usage.total_tokens}
- Cached tokens: {self.usage.cached_tokens}
- Internal/thinking tokens: {self.usage.internal_thinking_tokens}
- Stream chunks: {len(self.chunks)}
        """.strip()


class TokenCollectorHandler:

    def __init__(self):
        self.token_usage = None
        self.collected = False
        self.debug_calls = []

    def __call__(self, result_or_chunk, current_result=None):
        try:
            call_info = {
                'type': type(result_or_chunk).__name__,
                'has_usage': hasattr(result_or_chunk, 'usage'),
                'has_content': hasattr(result_or_chunk, 'content'),
                'has_is_final': hasattr(result_or_chunk, 'is_final'),
            }

            if hasattr(result_or_chunk, 'usage'):
                usage_type = type(result_or_chunk.usage).__name__ if result_or_chunk.usage else 'None'
                call_info['usage_type'] = usage_type

            self.debug_calls.append(call_info)

            if hasattr(result_or_chunk, 'usage') and hasattr(result_or_chunk, 'content'):
                self._store_usage(result_or_chunk.usage)
                return

            if hasattr(result_or_chunk, 'is_final') and result_or_chunk.is_final:
                if hasattr(result_or_chunk, 'usage') and result_or_chunk.usage:
                    self._store_usage(result_or_chunk.usage)
                return

            if hasattr(result_or_chunk, 'content') and hasattr(result_or_chunk, 'is_thinking'):
                return

        except Exception as e:
            print(f"ERROR in TokenCollector.__call__: {e}")

    def on_complete(self, result):
        try:
            if hasattr(result, 'usage') and result.usage:
                self._store_usage(result.usage)
            else:
                print(f"DEBUG: on_complete - no usage data available")

        except Exception as e:
            print(f"ERROR in TokenCollector.on_complete: {e}")

    def on_chunk(self, chunk, current_result=None):
        self.__call__(chunk, current_result)

    def on_error(self, error: str):
        print(f"TokenCollector.on_error: {error}")

    def _store_usage(self, usage):
        try:
            if usage is None:
                return

            if self.collected:
                return

            if hasattr(usage, 'total_tokens'):
                if usage.total_tokens > 0:
                    self.token_usage = {
                        'prompt_tokens': getattr(usage, 'prompt_tokens', 0),
                        'completion_tokens': getattr(usage, 'completion_tokens', 0),
                        'total_tokens': getattr(usage, 'total_tokens', 0),
                        'cached_tokens': getattr(usage, 'cached_tokens', 0),
                        'internal_thinking_tokens': getattr(usage, 'internal_thinking_tokens', 0)
                    }
                    self.collected = True
                    return
                else:
                    print(f"WARNING: Total tokens is 0, not storing: {usage}")
                    return

            elif isinstance(usage, dict):
                if usage.get('total_tokens', 0) > 0:
                    self.token_usage = {
                        'prompt_tokens': usage.get('prompt_tokens', 0),
                        'completion_tokens': usage.get('completion_tokens', 0),
                        'total_tokens': usage.get('total_tokens', 0),
                        'cached_tokens': usage.get('cached_tokens', 0),
                        'internal_thinking_tokens': usage.get('internal_thinking_tokens', 0)
                    }
                    self.collected = True
                    return
                else:
                    print(f"WARNING: Dict total tokens is 0: {usage}")
                    return

        except Exception as e:
            traceback.print_exc()

    def get_token_usage(self) -> Optional[Dict[str, int]]:
        return self.token_usage


class GeminiAIStudio:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("API key is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def _extract_usage_metrics(self, response) -> TokenUsage:
        usage = TokenUsage()

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            metadata = response.usage_metadata

            prompt_count = getattr(metadata, 'prompt_token_count', None)
            if prompt_count is not None:
                usage.prompt_tokens = int(prompt_count)

            completion_count = getattr(metadata, 'candidates_token_count', None)
            if completion_count is not None:
                usage.completion_tokens = int(completion_count)

            total_count = getattr(metadata, 'total_token_count', None)
            if total_count is not None:
                usage.total_tokens = int(total_count)

            cached_count = getattr(metadata, 'cached_content_token_count', None)
            if cached_count is not None:
                usage.cached_tokens = int(cached_count)

            if usage.total_tokens >= (usage.prompt_tokens + usage.completion_tokens):
                usage.internal_thinking_tokens = usage.total_tokens - (usage.prompt_tokens + usage.completion_tokens)
            else:
                usage.internal_thinking_tokens = 0

        return usage

    def _estimate_tokens_for_chunk(self, text: str, total_completion_tokens: int, total_content_length: int) -> int:
        if not text or total_content_length == 0:
            return 0

        chunk_ratio = len(text) / total_content_length
        estimated_tokens = int(total_completion_tokens * chunk_ratio)
        return max(1, estimated_tokens)

    def _process_response_parts(self, response_or_chunk) -> tuple[str, str]:
        thinking = ""
        content = ""

        candidates = getattr(response_or_chunk, 'candidates', [])
        if not candidates:
            return thinking, content

        candidate = candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            return thinking, content

        full_text = ""
        if hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    full_text += part.text
        elif hasattr(candidate.content, 'text'):
            full_text = candidate.content.text

        think_pattern = r'<Think>(.*?)</Think>'
        think_matches = re.findall(think_pattern, full_text, re.DOTALL | re.IGNORECASE)

        if think_matches:
            thinking = '\n'.join(think_matches).strip()
            content = re.sub(think_pattern, '', full_text, flags=re.DOTALL | re.IGNORECASE).strip()
        else:
            content = full_text

        return thinking, content

    def _prepare_config(self, **generation_config) -> Dict[str, Any]:
        config_params = {
            'temperature': generation_config.get('temperature', 0.7),
            'top_p': generation_config.get('top_p', 0.95),
            'top_k': generation_config.get('top_k', 40),
            'candidate_count': generation_config.get('candidate_count', 1),
            'max_output_tokens': generation_config.get('max_output_tokens', 8192),
        }

        stop_sequences = generation_config.get('stop_sequences', [])
        if stop_sequences:
            config_params['stop_sequences'] = stop_sequences

        if 'thinking_budget' in generation_config:
            config_params['thinking_config'] = types.ThinkingConfig(
                thinking_budget=generation_config['thinking_budget']
            )

        return config_params

    def _prepare_messages_with_thinking_prompt(self,
                                               messages: Union[str, List[Dict[str, Any]]],
                                               include_thinking: bool) -> Union[str, List[Dict[str, Any]]]:
        if not include_thinking:
            return messages

        thinking_instruction = """If you need to think through your response, wrap your thinking in <Think></Think> tags before giving your final answer."""

        if isinstance(messages, str):
            return messages + thinking_instruction
        elif isinstance(messages, list):
            modified_messages = messages.copy()
            for i in range(len(modified_messages) - 1, -1, -1):
                if modified_messages[i].get('role') == 'user':
                    current_content = modified_messages[i].get('content', '')
                    if isinstance(current_content, list):
                        found_text_part = False
                        for part in current_content:
                            if isinstance(part, dict) and part.get('text'):
                                part['text'] += thinking_instruction
                                found_text_part = True
                                break
                        if not found_text_part:
                            modified_messages[i]['content'].append({'text': thinking_instruction})
                    else:
                        modified_messages[i]['content'] = current_content + thinking_instruction
                    break
            return modified_messages

    async def generate_content(
            self,
            messages: Union[str, List[Dict[str, Any]]],
            stream: bool = True,
            include_thinking: bool = True,
            callback: Optional[Union[TokenCollectorHandler, type]] = None,
            **generation_config
    ) -> ContentResult:
        if callback is None:
            handler = TokenCollectorHandler()
        elif isinstance(callback, type):
            handler = callback()
        elif hasattr(callback, 'on_chunk'):
            handler = callback
        else:
            handler = TokenCollectorHandler()

        try:
            modified_messages = self._prepare_messages_with_thinking_prompt(messages, include_thinking)
            config = self._prepare_config(**generation_config)

            if stream:
                return await self._create_streaming_async(modified_messages, config, handler)
            else:
                return await self._create_sync_async(modified_messages, config, handler)

        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            handler.on_error(error_msg)
            return ContentResult(
                prompt=str(messages),
                thinking="",
                content="",
                usage=TokenUsage(),
                chunks=[],
                error=error_msg
            )

    async def async_generate_content(
            self,
            messages: Union[str, List[Dict[str, Any]]],
            include_thinking: bool = False,
            callback=None,
            **generation_config
    ):
        modified_messages = self._prepare_messages_with_thinking_prompt(messages, include_thinking)
        config = self._prepare_config(**generation_config)

        chunks_collected = []
        thinking_total = ""
        content_total = ""
        last_response_for_usage = None
        error_occurred = None
        chunk_id = 0

        try:
            generation_config_obj = types.GenerateContentConfig(**config)
            api_contents = self._prepare_api_contents(modified_messages)

            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=api_contents,
                config=generation_config_obj
            )

            for chunk_response in stream:
                last_response_for_usage = chunk_response
                thinking_chunk, content_chunk = self._process_response_parts(chunk_response)

                thinking_total += thinking_chunk
                content_total += content_chunk

                if thinking_chunk:
                    thinking_stream_chunk = StreamChunk(
                        content=thinking_chunk,
                        is_thinking=True,
                        estimated_tokens=0,
                        chunk_id=chunk_id,
                        usage=None,
                        is_final=False
                    )
                    chunks_collected.append(thinking_stream_chunk)

                    if callback and hasattr(callback, 'on_chunk'):
                        callback.on_chunk(thinking_stream_chunk, None)
                    elif callback and callable(callback):
                        callback(thinking_stream_chunk, None)

                    yield thinking_stream_chunk
                    chunk_id += 1

                if content_chunk:
                    content_stream_chunk = StreamChunk(
                        content=content_chunk,
                        is_thinking=False,
                        estimated_tokens=0,
                        chunk_id=chunk_id,
                        usage=None,
                        is_final=False
                    )
                    chunks_collected.append(content_stream_chunk)

                    if callback and hasattr(callback, 'on_chunk'):
                        callback.on_chunk(content_stream_chunk, None)
                    elif callback and callable(callback):
                        callback(content_stream_chunk, None)

                    yield content_stream_chunk
                    chunk_id += 1

        except Exception as e:
            error_msg = f"Streaming failed: {str(e)}"
            error_occurred = error_msg
            if callback and hasattr(callback, 'on_error'):
                callback.on_error(error_msg)
            print(f"Error during streaming: {error_msg}")

        finally:
            final_usage = TokenUsage()
            if last_response_for_usage:
                final_usage = self._extract_usage_metrics(last_response_for_usage)
                # print(f"DEBUG: Extracted usage metrics: {final_usage.to_dict()}")

            total_content_length = len(thinking_total) + len(content_total)
            if total_content_length > 0 and final_usage.completion_tokens > 0:
                for chunk in chunks_collected:
                    chunk.estimated_tokens = self._estimate_tokens_for_chunk(
                        chunk.content,
                        final_usage.completion_tokens,
                        total_content_length
                    )
                    chunk.usage = final_usage

            final_chunk = StreamChunk(
                content="",
                is_thinking=False,
                estimated_tokens=0,
                chunk_id=chunk_id,
                usage=final_usage,
                is_final=True
            )
            chunks_collected.append(final_chunk)

            final_result = ContentResult(
                prompt=str(modified_messages),
                thinking=thinking_total.strip(),
                content=content_total.strip(),
                usage=final_usage,
                chunks=chunks_collected,
                error=error_occurred
            )

            if callback:
                if hasattr(callback, 'on_complete'):
                    callback.on_complete(final_result)
                elif hasattr(callback, '__call__'):
                    callback(final_result)
                else:
                    print("Warning: Callback provided but no suitable method found")

            yield final_chunk

    def _prepare_api_contents(self, messages):
        if isinstance(messages, str):
            return [types.Part(text=messages)]
        elif isinstance(messages, list):
            processed_messages = []
            for msg in messages:
                if msg.get('role') == 'user':
                    content_parts = msg.get('content')
                    if isinstance(content_parts, str):
                        processed_messages.append({'role': 'user', 'parts': [types.Part(text=content_parts)]})
                    elif isinstance(content_parts, list):
                        parts_list = []
                        for part in content_parts:
                            if isinstance(part, dict) and part.get('text'):
                                parts_list.append(types.Part(text=part['text']))
                            elif isinstance(part, dict) and part.get('image_data'):
                                parts_list.append(types.Part(
                                    inline_data=types.Blob(
                                        mime_type='image/jpeg',
                                        data=base64.b64decode(part['image_data'])
                                    )
                                ))
                        processed_messages.append({'role': 'user', 'parts': parts_list})
                    else:
                        processed_messages.append(msg)
                elif msg.get('role') == 'model':
                    content_parts = msg.get('content')
                    if isinstance(content_parts, str):
                        processed_messages.append({'role': 'model', 'parts': [types.Part(text=content_parts)]})
                    elif isinstance(content_parts, list):
                        parts_list = []
                        for part in content_parts:
                            if isinstance(part, dict) and part.get('text'):
                                parts_list.append(types.Part(text=part['text']))
                        processed_messages.append({'role': 'model', 'parts': parts_list})
                    else:
                        processed_messages.append(msg)
                else:
                    processed_messages.append(msg)
            return processed_messages
        return messages

    async def _create_streaming_async(
            self,
            prompt: Union[str, List[Dict[str, Any]]],
            config: Dict[str, Any],
            handler: TokenCollectorHandler
    ) -> ContentResult:
        chunks = []
        thinking_total = ""
        content_total = ""
        usage = TokenUsage()
        last_response = None
        chunk_id = 0

        try:
            generation_config_obj = types.GenerateContentConfig(**config)
            api_contents = self._prepare_api_contents(prompt)

            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=api_contents,
                config=generation_config_obj
            )

            for chunk_response in stream:
                last_response = chunk_response
                thinking_chunk, content_chunk = self._process_response_parts(chunk_response)

                thinking_total += thinking_chunk
                content_total += content_chunk

                if thinking_chunk:
                    thinking_stream_chunk = StreamChunk(
                        content=thinking_chunk,
                        is_thinking=True,
                        estimated_tokens=0,
                        chunk_id=chunk_id
                    )
                    chunks.append(thinking_stream_chunk)

                    current_result = ContentResult(
                        prompt=str(prompt),
                        thinking=thinking_total,
                        content=content_total,
                        usage=usage,
                        chunks=chunks.copy()
                    )
                    handler(thinking_stream_chunk, current_result)
                    chunk_id += 1

                if content_chunk:
                    content_stream_chunk = StreamChunk(
                        content=content_chunk,
                        is_thinking=False,
                        estimated_tokens=0,
                        chunk_id=chunk_id
                    )
                    chunks.append(content_stream_chunk)

                    current_result = ContentResult(
                        prompt=str(prompt),
                        thinking=thinking_total,
                        content=content_total,
                        usage=usage,
                        chunks=chunks.copy()
                    )
                    handler(content_stream_chunk, current_result)
                    chunk_id += 1

            if last_response:
                usage = self._extract_usage_metrics(last_response)

                total_content_length = len(thinking_total) + len(content_total)
                if total_content_length > 0 and usage.completion_tokens > 0:
                    for chunk in chunks:
                        chunk.estimated_tokens = self._estimate_tokens_for_chunk(
                            chunk.content,
                            usage.completion_tokens,
                            total_content_length
                        )

        except Exception as e:
            error_msg = f"Streaming failed: {str(e)}"
            handler.on_error(error_msg)
            return ContentResult(
                prompt=str(prompt),
                thinking="",
                content="",
                usage=TokenUsage(),
                chunks=[],
                error=error_msg
            )

        result = ContentResult(
            prompt=str(prompt),
            thinking=thinking_total.strip(),
            content=content_total.strip(),
            usage=usage,
            chunks=chunks
        )
        handler.on_complete(result)
        return result

    async def _create_sync_async(
            self,
            prompt: Union[str, List[Dict[str, Any]]],
            config: Dict[str, Any],
            handler: TokenCollectorHandler
    ) -> ContentResult:
        try:
            generation_config_obj = types.GenerateContentConfig(**config)
            api_contents = self._prepare_api_contents(prompt)

            response = self.client.models.generate_content(
                model=self.model,
                contents=api_contents,
                config=generation_config_obj
            )

            thinking, content = self._process_response_parts(response)
            usage = self._extract_usage_metrics(response)

            chunks = []
            chunk_id = 0
            total_content_length = len(thinking) + len(content)

            if thinking:
                thinking_tokens = self._estimate_tokens_for_chunk(
                    thinking, usage.completion_tokens, total_content_length
                )
                thinking_chunk = StreamChunk(
                    content=thinking,
                    is_thinking=True,
                    estimated_tokens=thinking_tokens,
                    chunk_id=chunk_id
                )
                chunks.append(thinking_chunk)
                chunk_id += 1

            if content:
                content_tokens = self._estimate_tokens_for_chunk(
                    content, usage.completion_tokens, total_content_length
                )
                content_chunk = StreamChunk(
                    content=content,
                    is_thinking=False,
                    estimated_tokens=content_tokens,
                    chunk_id=chunk_id
                )
                chunks.append(content_chunk)

            result = ContentResult(
                prompt=str(prompt),
                thinking=thinking.strip(),
                content=content.strip(),
                usage=usage,
                chunks=chunks
            )

            for chunk in chunks:
                handler(chunk, result)
            handler.on_complete(result)
            return result

        except Exception as e:
            error_msg = f"Sync generation failed: {str(e)}"
            handler.on_error(error_msg)
            return ContentResult(
                prompt=str(prompt),
                thinking="",
                content="",
                usage=TokenUsage(),
                chunks=[],
                error=error_msg
            )
