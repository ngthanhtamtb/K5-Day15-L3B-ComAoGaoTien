import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, AsyncGenerator, Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.pptagent.slide_generator import AIPPTGenerator
from app.core.pptagent.schemas import SlideEnrichmentRequest
from app.services.ai.base import BaseAIService
from app.utils.pptx_utils import encode_response_data

logger = logging.getLogger(__name__)


class SlideEnrichmentDataService:
    def __init__(self):
        pass

    def _generate_uuid_if_none(self, value: Any) -> str:
        if not value:
            return str(uuid.uuid4())
        return str(value)

    async def stream_slide_data(
            self,
            slide_data: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        try:
            if not slide_data or "slides" not in slide_data:
                yield json.dumps({
                    "event": "error",
                    "message": "Invalid input: 'slides' key is missing or structure is empty."
                })
                return

            slides = slide_data.get("slides", [])
            presentation_id = self._generate_uuid_if_none(slide_data.get("presentation_id"))
            language = slide_data.get("language", "en")  # Default to English



            yield json.dumps({
                "event": "start",
                "presentation_id": presentation_id,
                "message": "Slide streaming started.",
                # "timestamp": asyncio.get_event_loop().time()
            })
            await asyncio.sleep(0.01)

            slide_idx = 0
            for slide in slides:
                try:
                    slide_id = str(uuid.uuid4())
                    slide_copy = slide.copy()
                    slide_copy["id"] = slide_id

                    yield json.dumps({
                        "event": "slide_page",
                        "presentation_id": presentation_id,
                        "slide_index": slide_idx,
                        "data": encode_response_data({
                            "id": slide_id,
                            "elements": [],
                            "background": slide_copy.get("background"),
                            "type": slide_copy.get("type", "content"),

                            **{k: v for k, v in slide_copy.items()
                               if k not in ["id", "elements", "background", "type"]}
                        })
                    })
                    await asyncio.sleep(0.1)

                    elements = slide_copy.get("elements", [])

                    for element_idx, element in enumerate(elements):
                        element_copy = element.copy()
                        element_copy["id"] = str(uuid.uuid4())

                        yield json.dumps({
                            "event": "element",
                            "presentation_id": presentation_id,
                            "id": slide_id,
                            "slide_index": slide_idx,
                            "element_index": element_idx,
                            "data": encode_response_data(element_copy)
                        })
                        await asyncio.sleep(0.1)

                    await asyncio.sleep(0.05)
                    slide_idx += 1

                except Exception as e:
                    logger.error(f"Error processing slide {slide_idx}: {str(e)}")
                    yield json.dumps({
                        "event": "error",
                        "slide_index": slide_idx,
                        "slide_id": slide.get("id", f"slide_{slide_idx + 1}"),
                        "error": str(e),
                        "message": f"Error processing slide {slide_idx + 1}: {str(e)}"
                    })
                    await asyncio.sleep(0.01)

            yield json.dumps({
                "event": "done",
                "presentation_id": presentation_id,
                "message": "All elements generated successfully."
            })

        except Exception as e:
            logger.error(f"Error in slide streaming: {str(e)}", exc_info=True)
            yield json.dumps({
                "event": "error",
                "presentation_id": slide_data.get("presentation_id", "unknown"),
                "status_code": 500,
                "message": f"Streaming failed: {str(e)}"
            })


class SlideEnrichmentService(BaseAIService):
    def __init__(self):
        super().__init__()
        self.agent = AIPPTGenerator(api_key=settings.GEMINI_API_KEY)
        self.target_width = 1000.0
        self.target_height = 562.5

    def _encode_response_data(self, data: Any) -> Any:
        return data

    async def enrich_slides_stream(
            self,
            slide_data: Dict[str, Any],
            enrich_req: SlideEnrichmentRequest
    ) -> AsyncGenerator[str, None]:
        try:
            if not slide_data or "slides" not in slide_data:
                yield json.dumps({
                    "event": "error",
                    "message": "Invalid input: 'slides' key is missing or structure is empty."
                })
                return

            slides_from_input: List[Dict] = slide_data.get("slides", [])
            presentation_id = slide_data.get("presentation_id", "unknown")

            yield json.dumps({
                "event": "start",
                "presentation_id": presentation_id,
                "message": "Slide enrichment started.",
                "timestamp": asyncio.get_event_loop().time()
            })
            await asyncio.sleep(0.01)

            initial_metadata = {
                "presentation_id": presentation_id,
                "title": slide_data.get("title", "Untitled Presentation"),
                "width": slide_data.get("width", self.target_width),
                "height": slide_data.get("height", self.target_height),
                "total_slides": len(slides_from_input),
                "model": enrich_req.model
            }
            yield json.dumps({
                "event": "metadata",
                "data": initial_metadata,
                "message": f"Processing {len(slides_from_input)} slides with {enrich_req.model}"
            })
            await asyncio.sleep(0.01)

            yield json.dumps({
                "event": "validation",
                "presentation_id": presentation_id,
                "message": "Validating slide structure..."
            })
            await asyncio.sleep(0.01)

            processed_slides = await self._validate_and_correct_cover_end(slides_from_input)

            slide_idx = 0
            for idx, slide in enumerate(processed_slides):
                try:
                    slide_id = slide.get("id", f"slide_{idx + 1}")

                    enriched_slide = await self._process_single_slide(slide, idx, enrich_req)

                    yield json.dumps({
                        "event": "slide_page",
                        "presentation_id": presentation_id,
                        "slide_index": slide_idx,
                        "data": self._encode_response_data({
                            "id": enriched_slide.get("id"),
                            "elements": [],
                            "background": enriched_slide.get("background"),
                            "type": enriched_slide.get("type"),
                            "width": enriched_slide.get("width", self.target_width),
                            "height": enriched_slide.get("height", self.target_height),
                            "sectionTag": enriched_slide.get("sectionTag")
                        })
                    })
                    await asyncio.sleep(0.1)

                    elements = enriched_slide.get("elements", [])
                    for element_idx, element in enumerate(elements):
                        yield json.dumps({
                            "event": "element",
                            "presentation_id": presentation_id,
                            "id": enriched_slide.get("id"),
                            "slide_index": slide_idx,
                            "element_index": element_idx,
                            "data": self._encode_response_data(element)
                        })
                        await asyncio.sleep(0.3)

                    await asyncio.sleep(0.3)
                    slide_idx += 1

                except Exception as e:
                    logger.error(f"Error processing slide {idx}: {str(e)}")
                    yield json.dumps({
                        "event": "slide_error",
                        "slide_index": idx,
                        "slide_id": slide.get("id", f"slide_{idx + 1}"),
                        "error": str(e),
                        "message": f"Error processing slide {idx + 1}: {str(e)}"
                    })
                    await asyncio.sleep(0.01)

            yield json.dumps({
                "event": "done",
                "presentation_id": presentation_id,
                "message": "All elements generated successfully."
            })

        except HTTPException as e:
            yield json.dumps({
                "event": "error",
                "presentation_id": slide_data.get("presentation_id", "unknown"),
                "status_code": e.status_code,
                "message": e.detail
            })
        except Exception as e:
            logger.error(f"Error in slide enrichment: {str(e)}", exc_info=True)
            yield json.dumps({
                "event": "error",
                "presentation_id": slide_data.get("presentation_id", "unknown"),
                "status_code": 500,
                "message": f"Enrichment failed: {str(e)}"
            })

    async def _process_single_slide(
            self,
            slide: Dict[str, Any],
            idx: int,
            enrich_req: SlideEnrichmentRequest
    ) -> Dict[str, Any]:
        """
        Process a single slide completely and return the enriched slide.
        This replaces the streaming version for internal processing.
        """
        # Deep copy to avoid modifying original
        enriched_slide = json.loads(json.dumps(slide))

        # Infer slide type if not set
        if not enriched_slide.get("type"):
            slide_type = await self._infer_slide_type(enriched_slide, enrich_req.model)
            enriched_slide["type"] = slide_type

        # Build slide context for element classification
        slide_context = await self._build_slide_context(enriched_slide)

        # Process text elements
        elements = enriched_slide.get("elements", [])
        for element in elements:
            if element.get("type") == "text":
                text_type = await self._classify_text_element_type(element, slide_context, enrich_req.model)
                element["textType"] = text_type

        # Add section tags for transition slides
        if enriched_slide.get("type") == "transition":
            await self._add_section_tag(enriched_slide, idx)

        # Resize elements to target dimensions
        original_width = enriched_slide.get("width", self.target_width)
        original_height = enriched_slide.get("height", self.target_height)
        await self._resize_slide_elements(enriched_slide, original_width, original_height)

        # Update slide dimensions
        enriched_slide["width"] = self.target_width
        enriched_slide["height"] = self.target_height

        return enriched_slide

    # Keep all the existing helper methods unchanged
    async def _infer_slide_type(self, slide: Dict[str, Any], model: str) -> str:
        """Infer slide type using AI model."""
        elements = slide.get("elements", [])
        text_elements_info = []

        for el in elements:
            if el.get("type") == "text":
                info = self._parse_text_element_content(el)
                if info["text"]:
                    text_elements_info.append(info)

        if not text_elements_info:
            return "content"

        # Sort by font size for context
        text_elements_info.sort(key=lambda x: x["font_size"], reverse=True)
        context_texts = []

        for i, info in enumerate(text_elements_info[:5]):
            context_texts.append(
                f"Text {i + 1} (Font Size: {info['font_size']}px): \"{info['text']}\""
            )

        if len(text_elements_info) > 5:
            context_texts.append(f"And {len(text_elements_info) - 5} more text elements.")

        system_prompt = self._build_slide_type_classification_prompt()
        prompt = f"""
        Slide Text Elements:
        {chr(10).join(context_texts)}

        Consider the overall layout and content typical for these slide types.
        """

        try:
            result = await self.agent.generate_content(
                system_instruction=system_prompt,
                prompt=prompt,
                model=model,
                token_callback=self.token_collector
            )

            valid_types = ['cover', 'contents', 'transition', 'content', 'end']
            inferred_type = result.content.strip().lower() if hasattr(result, 'content') else str(
                result).strip().lower()

            return inferred_type if inferred_type in valid_types else self._fallback_infer_slide_type_heuristic(slide)

        except Exception as e:
            logger.warning(f"AI slide type inference failed: {e}, using fallback")
            return self._fallback_infer_slide_type_heuristic(slide)

    async def _classify_text_element_type(
            self,
            text_element: Dict[str, Any],
            slide_context: str,
            model: str
    ) -> str:
        """Classify text element type using AI model."""
        text_content = self._parse_text_element_content(text_element)["text"]
        font_size = self._parse_text_element_content(text_element)["font_size"]

        if not text_content:
            return "content"

        valid_text_types = [
            'title', 'subtitle', 'content', 'item', 'itemTitle',
            'notes', 'header', 'footer', 'partNumber', 'itemNumber'
        ]

        system_prompt = self._build_text_element_classification_prompt()
        prompt = f"""
        Text: "{text_content}"
        Font Size: {font_size}px
        Slide Context: {slide_context[:200]}...

        Valid types: {', '.join(valid_text_types)}
        """

        try:
            result = await self.agent.generate_content(
                system_instruction=system_prompt,
                prompt=prompt,
                model=model,
                token_callback=self.token_collector
            )

            raw_response = result.content if hasattr(result, 'content') else str(result)
            logger.info(f"Raw AI response for text classification: {raw_response}")

            inferred_type = self._extract_type_from_response(raw_response)
            logger.info(f"Extracted text type: {inferred_type}")

            # Normalize common variations
            type_mapping = {
                'itemtitle': 'itemTitle',
                'partnumber': 'partNumber',
                'itemnumber': 'itemNumber'
            }
            inferred_type = type_mapping.get(inferred_type.lower(), inferred_type)

            return inferred_type if inferred_type in valid_text_types else self._fallback_classify_text_element(
                text_element)

        except Exception as e:
            logger.warning(f"AI text classification failed: {e}, using fallback")
            return self._fallback_classify_text_element(text_element)

    def _extract_type_from_response(self, raw_response: str) -> str:
        """Extract type from AI response, handling both plain text and JSON formats."""
        try:
            if raw_response.strip().startswith('{') or raw_response.strip().startswith('```json'):
                if '```json' in raw_response:
                    json_start = raw_response.find('{')
                    json_end = raw_response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = raw_response[json_start:json_end]
                        parsed_json = json.loads(json_str)
                        return parsed_json.get('type', '').strip()
                    else:
                        return raw_response.strip()
                else:
                    parsed_json = json.loads(raw_response)
                    return parsed_json.get('type', '').strip()
            else:
                return raw_response.strip()
        except json.JSONDecodeError:
            return raw_response.strip()

    async def _validate_and_correct_cover_end(self, slides: List[Dict]) -> List[Dict]:
        """Ensure at least one cover and one end slide exist."""
        if not slides:
            return []

        modified_slides = json.loads(json.dumps(slides))

        has_cover = any(s.get("type") == "cover" for s in modified_slides)
        has_end = any(s.get("type") == "end" for s in modified_slides)

        if not has_cover:
            logger.info("No cover page found. Setting the first slide as 'cover'.")
            modified_slides[0]["type"] = "cover"

        if not has_end and len(modified_slides) > 1:
            logger.info("No end page found. Setting the last slide as 'end'.")
            modified_slides[-1]["type"] = "end"

        return modified_slides

    async def _build_slide_context(self, slide: Dict[str, Any]) -> str:
        """Build context string from slide text elements."""
        context_parts = []
        for el in slide.get("elements", []):
            if el.get("type") == "text" and el.get("content"):
                text = self._parse_text_element_content(el)["text"]
                if text:
                    context_parts.append(text)

        context = " ".join(context_parts)
        return context[:200] + "..." if len(context) > 200 else context

    async def _add_section_tag(self, slide: Dict[str, Any], index: int):
        """Add section tag for transition slides."""
        section_title = self._extract_section_title_from_elements(slide.get("elements", []))
        if section_title:
            import re
            clean_title = re.sub(r'[^a-zA-Z0-9_]', '', section_title.replace(' ', '_')).lower()[:20]
            slide["sectionTag"] = {
                "id": f"section_{index}_{clean_title}",
                "title": section_title
            }

    async def _resize_slide_elements(self, slide: Dict[str, Any], original_width: float, original_height: float):
        """Resize all elements in a slide to target dimensions."""
        if not original_width or not original_height:
            logger.warning(f"Invalid original dimensions: {original_width}x{original_height}")
            return

        scale_x = self.target_width / original_width
        scale_y = self.target_height / original_height
        scale_factor = min(scale_x, scale_y)

        for element in slide.get("elements", []):
            self._resize_element(element, scale_factor)

    def _resize_element(self, element: Dict[str, Any], scale_factor: float):
        """Resize individual element."""
        import re

        # Resize position and dimensions
        for prop in ['x', 'y', 'width', 'height']:
            if prop in element:
                element[prop] = element[prop] * scale_factor

        # Resize font for text elements
        if element.get("type") == "text" and element.get("content"):
            content = element["content"]
            font_match = re.search(r'font-size:\s*(\d+\.?\d*)px', content)

            if font_match:
                original_size = float(font_match.group(1))
                new_size = original_size * scale_factor
                element["content"] = re.sub(
                    r'font-size:\s*(\d+\.?\d*)px',
                    f'font-size:{new_size:.2f}px',
                    content
                )
            elif 'style="' in content:
                element["content"] = content.replace(
                    'style="',
                    f'style="font-size:{16 * scale_factor:.2f}px;'
                )
            else:
                element["content"] = f'<p style="font-size:{16 * scale_factor:.2f}px;">{content}</p>'

    def _parse_text_element_content(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Parse text element content to extract plain text and font size."""
        import re

        content = element.get("content", "")
        plain_text = re.sub(r'<[^>]+>', '', content).strip()

        font_size = 16.0  # default
        style_match = re.search(r'font-size:\s*(\d+\.?\d*)px', content)
        if style_match:
            try:
                font_size = float(style_match.group(1))
            except ValueError:
                pass

        return {"text": plain_text, "font_size": font_size}

    def _build_slide_type_classification_prompt(self) -> str:
        """Build system prompt for slide type classification."""
        return """
        You are an expert in presentation design and slide analysis. Your task is to classify presentation slides into specific types based on their text content and layout characteristics.

        Available slide types:
        - 'cover': Title slide, typically has large title text and minimal content
        - 'contents': Table of contents or agenda slide
        - 'transition': Section divider slides with section titles
        - 'content': Regular content slides with main information
        - 'end': Conclusion slides (Thank you, Questions, Contact, etc.)

        Analyze the provided text elements and their font sizes to determine the most appropriate slide type. Consider:
        1. Font sizes (larger fonts typically indicate titles or headers)
        2. Content patterns (lists suggest contents, "thank you" suggests end)
        3. Amount of text (cover slides have minimal text, content slides have more)
        4. Text positioning and hierarchy

        Respond with ONLY the slide type name (e.g., 'cover', 'content', etc.). Do not include explanations or JSON format.
        """

    def _build_text_element_classification_prompt(self) -> str:
        """Build system prompt for text element classification."""
        return """
        You are an expert in presentation design and typography. Your task is to classify individual text elements within presentation slides based on their content, font size, and context.

        Available text element types:
        - 'title': Main slide title (usually largest font, prominent position)
        - 'subtitle': Secondary title or subtitle text
        - 'content': Main body content, paragraphs, descriptions
        - 'item': List items, bullet points
        - 'itemTitle': Headers or titles for list sections
        - 'notes': Footnotes, references, small annotations
        - 'header': Page headers, slide numbers at top
        - 'footer': Page footers, copyright, slide numbers at bottom
        - 'partNumber': Section or part numbering
        - 'itemNumber': Numbering for list items

        Consider these factors:
        1. Font size (titles are larger, notes/footers are smaller)
        2. Content pattern (numbered lists, bullet points)
        3. Position context (headers at top, footers at bottom)
        4. Text length (titles are short, content is longer)
        5. Slide context (what other elements are present)

        Respond with ONLY the text element type name (e.g., 'title', 'content', etc.). Do not include explanations or JSON format.
        """

    def _fallback_classify_text_element(self, text_element: Dict[str, Any]) -> str:
        """Fallback heuristic for text element classification."""
        info = self._parse_text_element_content(text_element)
        font_size = info["font_size"]
        text = info["text"]

        if font_size >= 45:
            return "title"
        elif font_size >= 30:
            return "subtitle"
        else:
            import re
            if re.search(r'^\s*(\d+\.|[a-zA-Z]\)|[-*•])\s+', text):
                return "item"
            return "content"

    def _extract_section_title_from_elements(self, elements: List[Dict[str, Any]]) -> Optional[str]:
        """Extract section title from elements (largest text)."""
        text_elements = []
        for el in elements:
            if el.get("type") == "text":
                info = self._parse_text_element_content(el)
                if info["text"]:
                    text_elements.append(info)

        if text_elements:
            text_elements.sort(key=lambda x: x["font_size"], reverse=True)
            return text_elements[0]["text"]
        return None

    def _fallback_infer_slide_type_heuristic(self, slide) -> str:
        """
        A simplified heuristic-based fallback for slide type inference,
        used if the GenerativeModel call fails or is not available, or returns an invalid type.
        """
        elements = slide.get("elements", [])
        text_elements_info = []
        for el in elements:
            if el.get("type") == "text":
                info = self._parse_text_element_content(el)
                if info["text"]:
                    text_elements_info.append(info)

        if not text_elements_info:
            return "content"

        text_elements_info.sort(key=lambda x: x["font_size"], reverse=True)

        end_keywords = ["thank you", "ご清聴ありがとうございました", "questions", "ご質問", "cảm ơn", "liên hệ",
                        "the end"]
        for info in text_elements_info:
            if any(keyword in info["text"].lower() for keyword in end_keywords):
                return "end"

        main_title_font_size = text_elements_info[0]["font_size"] if text_elements_info else 0
        main_title_text = text_elements_info[0]["text"].lower() if text_elements_info else ""

        # Heuristic for cover page
        if main_title_font_size > 60 and len(text_elements_info) <= 3:
            return "cover"

        # Heuristic for contents page
        contents_keywords = ["table of contents", "mục lục", "contents", "nội dung chính", "chương trình"]
        if any(keyword in main_title_text or keyword in info["text"].lower() for info in text_elements_info for keyword
               in contents_keywords):
            return "contents"

        # Heuristic for transition page
        if 35 < main_title_font_size <= 60 and len(text_elements_info) <= 3:
            return "transition"

        return "content"  # Default fallback for any other slide