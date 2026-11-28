from typing import Dict, Any, Optional
from app.core.pptagent.types import OperateType
from app.core.pptagent.schemas import OutlineGenerateRequest, SlideImprovementContentRequest


class PromptBuilder:

    OUTLINE_SYSTEM_PROMPT = """
    You are an expert presentation designer and content strategist specialized in generating clear, 
    well-structured, and audience-appropriate slide outlines.
    """

    CONTENT_IMPROVEMENT_SYSTEM_PROMPT = """
    You are an expert in writing presentation content with expertise in improving clarity, 
    engagement, and professional communication across different styles and audiences.
    """

    TITLE_GENERATION_SYSTEM_PROMPT = """
    You are a helpful assistant that generates presentation titles.
    """

    SLIDE_GENERATION_SYSTEM_PROMPT = """
    You are an expert AI assistant specialized in creating slide presentation data in JSON format 
    for presentation tools. Your task is to create structured, professional slide content.
    """

    @staticmethod
    def build_outline_generation_prompt(outline_req: OutlineGenerateRequest) -> str:
        return f"""
        Generate a professional PowerPoint presentation outline for the topic: "{outline_req.content}"

        **AUDIENCE PROFILE:**
        Please tailor the content to the following target audience:
        - {outline_req.audience}
        Consider their background knowledge, interests, and expectations when crafting the structure and tone.

        **STYLE & TONE:**
        - Style: {outline_req.style} (e.g., academic, persuasive, informative, narrative, business-oriented)
        - Tone: {outline_req.tone} (e.g., formal, conversational, inspiring, authoritative)

        **REFERENCE MATERIALS:**
        The following content is extracted from relevant documents provided by the user. Use it as additional context to enhance the outline where applicable:
        {outline_req.document}

        **LANGUAGE & STRUCTURE:**
        - Language: {outline_req.language}
        - Maximum 3 hierarchical levels (Title → Chapter → Section)
        - Use standard markdown format
        - **IMPORTANT**: For languages with special characters (Japanese, Chinese, Korean, etc.), ensure proper spacing and formatting to prevent markdown line breaks

        **CONTENT & LAYOUT REQUIREMENTS:**
        1. **Title slide**: Concise and engaging, aligned with topic and audience
        2. **Main chapters**: 
           - Number of chapters: Adapt to topic complexity and audience needs
           - Chapter titles: Short, impactful, and style-aligned
           - Each chapter contains relevant sections based on document context
        3. **Bullet points**: 
           - Written as complete speaker notes (what presenter will say)
           - Length: Comprehensive but concise, suitable for slide presentation
           - Number of bullets: Adapt to section content needs
           - **Required**: Use numbered layout format (1, 1.1 style)

        **PROFESSIONAL SLIDE STANDARDS:**
        - Content must fit a single slide (no overcrowding)
        - Logical flow for easy audience understanding
        - Presentation length and detail adapted to audience and setting
        - Maintain professional but accessible language and structure

        **EXACT OUTPUT FORMAT:**

        # [Main Title - Compelling and Audience-Aligned]

        ## 1. [Chapter]
        ### 1.1 [Section 1]
        - [Complete bullet point suitable for speech on slide]
        - [Bullet point with specific insight or example]
        - [More bullet points if necessary for clarity and depth]

        ## [Additional Chapters...]
        [Continue with numbered format...]

        **AVOID THESE MISTAKES:**
        - Overly long or abstract titles
        - Vague, too short, or overly wordy bullet points
        - Slide content too dense for effective presentation
        - Incorrect numbering format (must follow 1, 1.1, 1.2, etc.)
        - **Markdown formatting issues**: Watch for spacing and line break errors, especially with CJK characters
        - Encoding problems or misplaced formatting characters

        **FORMATTING NOTES:**
        - Clean and consistent markdown structure
        - Adequate spacing around headings and bullets
        - Proper handling of special characters (especially CJK)
        - Consistent formatting across all chapters

        Output only the markdown outline. Do not include additional explanations or commentary.
        """

    @staticmethod
    def build_title_presentation_prompt(outline: str, language: str, **kwargs) -> str:
        return f"""
            Create a short presentation title from this outline: {outline}
            Rules:
            - Maximum 8 words only
            - No punctuation marks (:, -, etc.)
            - No subtitles or explanations
            - Just the core topic
            - Language: {language}

            Example: "Digital Marketing Strategy" not "Digital Marketing Strategy: Modern Approaches"
        """

    @staticmethod
    def build_slide_generation_prompt(outline: str, document: str,
                                      language: str, topic: str, slide_count: int,
                                      remove_numbering: bool = True, **kwargs) -> str:
        style = kwargs.get('style', 'professional')
        audience = kwargs.get('audience', 'general')
        tone = kwargs.get('tone', 'formal')

        return f"""
            Bạn là một trợ lý AI chuyên tạo dữ liệu slide trình bày dưới định dạng JSON cho công cụ PPT.
            Nhiệm vụ của bạn là tạo dữ liệu JSON cho **page slide trình bày** của một bài thuyết trình, dựa trên các chi tiết được cung cấp.

            **PRESENTATION CONTEXT:**
            - Topic: {topic}
            - Language: {language}
            - Style: {style}
            - Audience: {audience}
            - Tone: {tone}

            **REFERENCE MATERIALS:**
            The following content is extracted from relevant documents provided by the user. Use it as additional context to enhance the writing where applicable:
            {document}

            **QUAN TRỌNG: Format Output**
            - Mỗi slide PHẢI được bọc trong cặp thẻ <slide> và </slide>
            - Mỗi cặp thẻ chỉ chứa MỘT slide duy nhất
            - Không sử dụng markdown code blocks ```json
            - Trả về từng slide một cách tuần tự

            **Ví dụ format chính xác:**
            <slide>
            {{"type": "cover", "data": {{"title": "Tiêu đề", "text": "Mô tả"}}}}
            </slide>

            <slide>
            {{"type": "contents", "data": {{"items": ["Mục 1", "Mục 2"]}}}}
            </slide>

            **Hướng dẫn Chung:**
            1. CHỈ tạo đối tượng JSON cho loại slide và nội dung được yêu cầu.
            2. Tất cả nội dung văn bản phải bằng ngôn ngữ {language}.
            3. Đảm bảo nội dung mạch lạc, chuyên nghiệp và phù hợp với chủ đề "{topic}".
            4. Tổng số slide PHẢI là {slide_count}.
            5. Nội dung phải phù hợp với style "{style}" và tone "{tone}" cho audience "{audience}".

            **Loại page Slide được Yêu cầu:** ['cover', 'contents', 'transition', 'content', 'end']

            **Quy tắc Cụ thể cho Cấu trúc Slide:**
            -   **Slide đầu tiên (slide 1)** PHẢI là loại **"cover"**.
                * Nó nên có một tiêu đề chính và một đoạn văn mô tả ngắn gọn cho bài thuyết trình về "{topic}".
                * **Ví dụ:** {{"type": "cover", "data": {{"title": "Tiêu đề Bài Thuyết Trình", "text": "Mô tả ngắn gọn về chủ đề."}}}}
            -   **Slide thứ hai (slide 2)** PHẢI là loại **"contents"**.
                * Nó nên liệt kê tất cả các phần nội dung chính (agenda) của bài thuyết trình.
                * **Các mục trong "items" của slide này PHẢI là các tiêu đề chính của từng phần nội dung.**
                * **Ví dụ:** {{"type": "contents", "data": {{"items": ["Phần Giới Thiệu", "Phần Nội Dung Chính", "Phần Kết Luận"]}}}}
            -   **Các slide chuyển tiếp (transition)**:
                * Đặt slide chuyển tiếp này NGAY TRƯỚC các slide nội dung của phần đó.
                * **Tiêu đề (`title`) của slide `transition` PHẢI giống hoặc đồng nghĩa với mục đã được liệt kê trong slide `contents` trước đó.**
                * **Ví dụ:** {{"type": "transition", "data": {{"title": "Khám Phá Phần Tiếp Theo", "text": "Đi sâu vào chi tiết của chủ đề."}}}}
            -   **Các slide nội dung (content)**:
                * Mở rộng hơn để có được nội dung chi tiết, hấp dẫn.
                * Mảng "items" PHẢI có từ 2 đến 4 phần tử.
                * Mỗi phần tử trong mảng "items" PHẢI có một "title" ngắn gọn, dễ hiểu và "text" giải thích chi tiết.
                * **Ví dụ:** {{"type": "content", "data": {{"title": "Điểm Nổi Bật", "items": [{{"title": "Yếu Tố 1", "text": "Giải thích chi tiết."}}, {{"title": "Yếu Tố 2", "text": "Mở rộng ý."}}]}}}}
            -   **Slide cuối cùng** PHẢI là loại **"end"**.
                * Nó nên chứa một thông điệp kết thúc phù hợp với tone "{tone}".
                * **Ví dụ:** {{"type": "end", "data": {{"title": "Cảm Ơn Quý Vị", "text": "Xin trân trọng cảm ơn sự lắng nghe của quý vị!"}}}}

            **Lưu ý Quan trọng:**
            - Tất cả nội dung cụ thể của slide phải được lồng bên trong trường "data".
            - Mỗi slide phải được bọc trong <slide></slide> riêng biệt
            - Không được gộp nhiều slide trong một cặp thẻ
            - Nội dung phải phù hợp với audience "{audience}" và style "{style}"

            **Cách xử lý Dàn Ý:**
            - Dàn ý dưới đây được viết theo chuẩn markdown có thể bao gồm đánh số ở đầu các mục như "1.", "1.1.", v.v.
            - Nếu người dùng yêu cầu loại bỏ đánh số (remove_numbering=True), hãy **bỏ qua tất cả phần đánh số đầu dòng khi tạo nội dung slide**. Chỉ giữ lại tiêu đề chính xác.

            **Trạng thái yêu cầu remove numbering từ client: {remove_numbering}**

            ```markdown
            {outline}
            ```

            Hãy bắt đầu tạo {slide_count} slides ngay bây giờ, mỗi slide trong một cặp thẻ <slide></slide> riêng biệt:
            """

    @staticmethod
    def build_content_improvement_prompt(improve_req: SlideImprovementContentRequest,
                                         extracted_text: str) -> str:
        return f"""
        You are an expert in writing presentation content.
        Rewrite the following slide text to improve clarity and fluency, using a {improve_req.style} style and a(n) {improve_req.tone} tone.

        **PRESENTATION CONTEXT:**
        - Audience: {improve_req.audience}
        - Topic: {improve_req.topic}
        - Language: {improve_req.language}
        - Style: {improve_req.style}
        - Tone: {improve_req.tone}

        **CURRENT SLIDE LAYOUT CONTEXT:**
        {improve_req.current_layout}

        **IMPROVEMENT GUIDELINES:**
        - Keep the original meaning intact
        - Do not expand, shorten significantly, or add new ideas
        - Maintain the core message while improving clarity and engagement
        - Ensure the text fits well within the slide layout context
        - Use language appropriate for the specified audience
        - Apply the requested style and tone consistently

        **OUTPUT REQUIREMENTS:**
        - Return only the revised text
        - No explanation or formatting
        - Preserve any necessary HTML structure if applicable
        - Ensure text flows naturally and professionally

        **Text to rewrite:**
        "{extracted_text}"
        """

    @staticmethod
    def build_text_enhancement_prompt(text: str, style: str, tone: str,
                                      language: str = "English", **kwargs) -> str:
        enhancement_type = kwargs.get('enhancement_type', 'general improvement')
        audience = kwargs.get('audience', 'general audience')

        return f"""
        Enhance the following text to be more engaging and professional.

        **ENHANCEMENT PARAMETERS:**
        - Target Style: {style}
        - Desired Tone: {tone}
        - Language: {language}
        - Enhancement Type: {enhancement_type}
        - Target Audience: {audience}

        **ENHANCEMENT GUIDELINES:**
        - Improve clarity and readability
        - Make the text more engaging while maintaining professionalism
        - Ensure the enhanced text matches the specified style and tone
        - Keep the core message and meaning intact
        - Adapt language complexity for the target audience

        **Original Text:**
        {text}

        **Enhanced Text:**
        """

    @staticmethod
    def build_slide_restructure_prompt(slide_content: str, new_structure: str,
                                       language: str = "English") -> str:
        return f"""
        Restructure the following slide content according to the new structure requirements.

        **RESTRUCTURING PARAMETERS:**
        - Target Language: {language}
        - New Structure: {new_structure}

        **RESTRUCTURING GUIDELINES:**
        - Maintain all important information from the original content
        - Reorganize content to fit the new structure
        - Ensure logical flow and coherence
        - Adapt formatting to match the new structure requirements

        **Original Content:**
        {slide_content}

        **Restructured Content:**
        """

    @staticmethod
    def build_slide_translation_prompt(content: str, source_language: str,
                                       target_language: str, style: str = "professional") -> str:
        return f"""
        Translate the following slide content from {source_language} to {target_language}.

        **TRANSLATION PARAMETERS:**
        - Source Language: {source_language}
        - Target Language: {target_language}
        - Style: {style}

        **TRANSLATION GUIDELINES:**
        - Maintain the professional presentation tone
        - Preserve the original meaning and context
        - Adapt cultural references appropriately
        - Ensure the translation sounds natural in the target language
        - Keep technical terms accurate
        - Maintain formatting and structure

        **Content to Translate:**
        {content}

        **Translation:**
        """

    @staticmethod
    def build_slide_summarization_prompt(content: str, target_length: str = "concise",
                                         language: str = "English") -> str:
        return f"""
        Summarize the following slide content to make it more {target_length}.

        **SUMMARIZATION PARAMETERS:**
        - Target Length: {target_length}
        - Language: {language}

        **SUMMARIZATION GUIDELINES:**
        - Preserve the most important points
        - Maintain clarity and coherence
        - Remove redundant or less critical information
        - Keep the professional tone
        - Ensure the summary is suitable for slide presentation

        **Original Content:**
        {content}

        **Summarized Content:**
        """

    @staticmethod
    def build_slide_expansion_prompt(content: str, expansion_focus: str,
                                     language: str = "English") -> str:
        return f"""
        Expand the following slide content with focus on {expansion_focus}.

        **EXPANSION PARAMETERS:**
        - Focus Area: {expansion_focus}
        - Language: {language}

        **EXPANSION GUIDELINES:**
        - Add relevant details and examples
        - Maintain the original message and tone
        - Ensure expanded content is still suitable for presentation
        - Keep information accurate and valuable
        - Maintain logical flow and structure

        **Original Content:**
        {content}

        **Expanded Content:**
        """

    @staticmethod
    def build_custom_prompt(template: str, variables: Dict[str, Any]) -> str:
        try:
            return template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing variable in prompt template: {e}")

    @classmethod
    def get_system_prompt(cls, operation_type: str) -> str:
        system_prompts = {
            OperateType.GENERATE_OUTLINE.value: cls.OUTLINE_SYSTEM_PROMPT,
            OperateType.IMPROVE_CONTENT.value: cls.CONTENT_IMPROVEMENT_SYSTEM_PROMPT,
            OperateType.GENERATE_TITLE_PRESENTATION.value: cls.TITLE_GENERATION_SYSTEM_PROMPT,
            OperateType.GENERATE_PRESENTATION.value: cls.SLIDE_GENERATION_SYSTEM_PROMPT,
        }
        return system_prompts.get(operation_type, "")

    @classmethod
    def validate_prompt_parameters(cls, operation_type: str, **kwargs) -> bool:
        required_params = {
            OperateType.GENERATE_OUTLINE.value: ["content", "audience", "style", "tone", "language"],
            OperateType.GENERATE_TITLE_PRESENTATION.value: ["outline", "language"],
            OperateType.GENERATE_PRESENTATION.value: ["outline", "language", "topic", "slide_count"],
            OperateType.IMPROVE_CONTENT.value: ["style", "tone", "audience", "topic", "language"],
        }

        if operation_type not in required_params:
            return True

        missing_params = [param for param in required_params[operation_type] if param not in kwargs]
        if missing_params:
            raise ValueError(f"Missing required parameters for {operation_type}: {missing_params}")

        return True
