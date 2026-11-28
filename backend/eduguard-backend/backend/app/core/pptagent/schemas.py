import uuid
from pydantic import BaseModel, Field, validator, field_validator, model_validator
from typing import Optional, List, Union, Dict, Any


class OutlineGenerateRequest(BaseModel):
    content: str = Field(..., description="Topic for the presentation outline")
    document: Optional[str] = Field(None, description="Document for the presentation outline")
    topic: Optional[str] = Field(default="general", description="")
    depth: Optional[int] = Field(default=2, ge=1, le=5)
    tone: Optional[str] = Field(default="neutral", description="")
    style: Optional[str] = Field(default="modern", description="")
    audience: Optional[str] = Field(default="general", description="")
    language: Optional[str] = Field(default="en", description="Language for the outline")
    model: Optional[str] = Field(default="gemini-2.5-flash", description="LLM model for the outline")
    include_thoughts: Optional[bool] = Field(default=False, description="COT")
    stream: Optional[bool] = Field(default=True, description="Whether to stream the response")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "content": "詳細な市場調査: 競争相手の分析、市場動向、顧客ニーズに至るまで、包括的な市場調査を行うことで、企業は正しい戦略的決定を下すことができます。",
                    "topic": "general",
                    "depth": 2,
                    "tone": "neutral",
                    "style": "modern",
                    "audience": "general",
                    "language": "en",
                    "stream": True
                }
            ]
        }


class OutlineResponse(BaseModel):
    outline: str


class AIGeneratePresentationRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title Presentation.")
    presentation_id: Optional[str] = Field(None, description="Presentation ID.")
    template_id: Union[uuid.UUID, str] = Field(..., description="ID of the presentation template (for UUID).")
    outline: Optional[str] = Field(None, description="Outline for generating AI slide content.")
    document: str = Field(None, description="Document for generating presentation")
    language: Optional[str] = Field("English", description="Language for the presentation content.")
    style: Optional[str] = Field("Professional",
                                 description="Overall style of the presentation (e.g., 'Professional', 'Creative', 'Minimalist').")
    audience: Optional[str] = Field("General Public", description="Target audience for the presentation.")
    topic: Optional[str] = Field("AI in Business", description="Main topic of the presentation.")
    tone: Optional[str] = Field("Informative",
                                description="Tone of the presentation (e.g., 'Informative', 'Persuasive', 'Casual').")
    image_urls: Optional[List[str]] = Field(None, description="List of image URLs to be used in the presentation.")
    slide_count: Optional[int] = Field(5, description="Maximum number of slides")
    ignore_pages: Optional[List[str]] = Field(None, description="")

    @model_validator(mode='before')
    @classmethod
    def generate_ids(cls, values):
        if isinstance(values, dict):
            if values.get('presentation_id') is None:
                values['presentation_id'] = str(uuid.uuid4())
        return values

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "template_id": "17c52447-6001-46b9-84fe-2a7ec13390d7",
                    "presentation_id": None,
                    "outline": """# 量子コンピュータの未来

    ## 1. 量子コンピュータの基礎
    ### 1.1 量子コンピュータとは
    - 量子コンピュータは、量子力学の原理を利用して計算を行う新しい計算機です。従来のコンピュータとは異なる原理で動作し、特定の問題に対して圧倒的な計算能力を発揮します。
    - 量子ビット（qubit）は、0と1の重ね合わせ状態を持つことができ、これにより並列計算が可能になります。
    - 量子コンピュータは、暗号解読、新薬開発、材料設計など、様々な分野への応用が期待されています。

    ### 1.2 量子コンピュータの原理
    - 量子コンピュータは、重ね合わせ、量子エンタングルメント、量子干渉という3つの主要な量子力学的原理に基づいています。
    - 重ね合わせは、量子ビットが0と1の両方の状態を同時に持つことができる性質です。
    - 量子エンタングルメントは、複数の量子ビットが互いに相関し、一方の状態が変化すると他方も瞬時に変化する現象です。
    - 量子干渉は、量子ビットの状態が互いに干渉し合い、特定の計算結果を強調する現象です。

    ### 1.3 量子コンピュータの種類
    - 量子コンピュータには、超伝導量子ビット、イオントラップ量子ビット、光量子ビットなど、様々な種類があります。
    - 超伝導量子ビットは、マイクロ波回路を用いて量子ビットを実現する方式で、大規模化に適しています。
    - イオントラップ量子ビットは、イオンを電磁場中に閉じ込め、レーザー光で制御する方式で、高い精度を実現できます。
    - 光量子ビットは、光子を用いて量子ビットを実現する方式で、長距離通信に適しています。

    ## 2. 量子コンピュータの現状
    ### 2.1 量子コンピュータの開発状況
    - 現在、Google、IBM、Microsoftなどの大手企業が量子コンピュータの開発に積極的に取り組んでいます。
    - これらの企業は、量子コンピュータのハードウェアだけでなく、ソフトウェアやアルゴリズムの開発も進めています。
    - 量子コンピュータの性能は、量子ビット数、コヒーレンス時間、ゲート忠実度などの指標で評価されます。

    ### 2.2 量子コンピュータの応用分野
    - 量子コンピュータは、暗号解読、新薬開発、材料設計、金融工学、人工知能など、様々な分野への応用が期待されています。
    - 暗号解読では、現在の暗号技術を破る可能性があり、新しい暗号技術の開発が急務となっています。
    - 新薬開発では、分子シミュレーションを用いて、より効率的に新薬を開発できる可能性があります。
    - 材料設計では、新しい材料の特性を予測し、より高性能な材料を開発できる可能性があります。

    ### 2.3 量子コンピュータの課題
    - 量子コンピュータは、量子ビットの安定性、大規模化、エラー訂正など、多くの課題を抱えています。
    - 量子ビットは、外部からのノイズに弱く、量子状態がすぐに壊れてしまうため、安定性を高める必要があります。
    - 量子ビット数を増やすためには、量子ビット間の接続性を高め、制御を容易にする必要があります。
    - 量子コンピュータは、計算中にエラーが発生しやすいため、エラー訂正技術を開発する必要があります。

    ## 3. 量子コンピュータの未来
    ### 3.1 量子コンピュータの将来展望
    - 量子コンピュータは、今後数十年で実用化されると予想されています。
    - 量子コンピュータが実用化されれば、社会や経済に大きな影響を与える可能性があります。
    - 量子コンピュータの発展には、ハードウェア、ソフトウェア、アルゴリズムの研究開発が不可欠です。

    ### 3.2 量子コンピュータと社会
    - 量子コンピュータは、医療、エネルギー、環境問題など、社会の様々な課題解決に貢献できる可能性があります。
    - 量子コンピュータの普及には、人材育成、倫理的な問題への対応、セキュリティ対策などが重要になります。
    - 量子コンピュータは、社会を変革する可能性を秘めていますが、その影響を十分に理解し、適切に活用する必要があります。

    ### 3.3 量子コンピュータの倫理
    - 量子コンピュータの発展は、倫理的な問題を引き起こす可能性があります。
    - 特に、暗号解読能力の向上は、プライバシーやセキュリティに深刻な影響を与える可能性があります。
    - 量子コンピュータの開発と利用においては、倫理的なガイドラインを策定し、責任ある行動を心がける必要があります。
    """,
                    "content": "Detailed data on market trends and financial forecasts.",
                    "document": None,
                    "language": "en",
                    "style": "Professional",
                    "audience": "Tech Enthusiasts",
                    "topic": "Future of Quantum Computing",
                    "tone": "Informative",
                    "image_urls": [
                        "https://images.unsplash.com/photo-1503023345310-bd7c1de61c7d",
                        "https://images.unsplash.com/photo-1518770660439-4636190af475",
                        "https://images.unsplash.com/photo-1498050108023-c5249f4df085"
                    ],
                    "slide_count": 15
                }
            ]
        }


class SlideImprovementContentRequest(BaseModel):
    text_to_improve: str = Field(..., description="The text on the slide page that needs improvement.")
    page_id: str = Field(None, description="Page Slide ID")
    element_id: str = Field(None, description="Element Slide ID")
    current_layout: Optional[str] = Field(None,
                                          description="Description of the current text layout on the slide (e.g., 'bullet points', 'short paragraph', 'title and subtitle').")
    language: Optional[str] = Field("en", description="Language for the presentation content (e.g., 'en', 'vi', 'jp').")
    style: Optional[str] = Field("Professional",
                                 description="Overall style of the presentation (e.g., 'Professional', 'Creative', 'Minimalist').")
    audience: Optional[str] = Field("General Public", description="Target audience for the presentation.")
    topic: Optional[str] = Field("AI in Business", description="Main topic of the presentation.")
    tone: Optional[str] = Field("Informative",
                                description="Tone of the presentation (e.g., 'Informative', 'Persuasive', 'Casual').")
    stream: Optional[bool] = Field(default=False)

    @model_validator(mode='before')
    @classmethod
    def generate_ids(cls, values):
        if isinstance(values, dict):
            if values.get('page_id') is None:
                values['page_id'] = str(uuid.uuid4())
            if values.get('element_id') is None:
                values['element_id'] = str(uuid.uuid4())
        return values

    class Config:
        json_schema_extra = {
            "examples": [
                {"page_id": None,
                 "element_id": None,
                 "text_to_improve": f"""<p style=""><strong><span style="font-size: 28px;"><span style="color: rgb(255, 255, 255);">洗練された市場調査で、戦略的意思決定を加速</span></span></strong></p>""",
                 "current_layout": None,
                 "language": "en",
                 "style": "Professional",
                 "audience": "General Public",
                 "topic": "AI in Business",
                 "tone": "Informative",
                 "stream": False
                 }
            ]
        }


class SlideEnrichmentRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Title Presentation.")
    presentation_id: Optional[str] = Field(default=None, description="Presentation ID.")
    slides: Optional[List[Dict[str, Any]]] = Field(default=None, description="")
    model: Optional[str] = Field(default="gemini-2.5-flash", description="AI model to use for enrichment")
    dump_input_json: Optional[bool] = Field(default=False, description="Dump json input slides")
    preserve_original_dimensions: Optional[bool] = Field(default=False, description="Keep original slide dimensions")

    @model_validator(mode='before')
    @classmethod
    def generate_ids(cls, values):
        if isinstance(values, dict):
            if values.get('presentation_id') is None:
                values['presentation_id'] = str(uuid.uuid4())
        return values


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for image generation", min_length=1, max_length=1000)
    number_of_images: int = Field(default=1, ge=1, le=4, description="Number of images to generate")
    aspect_ratio: str = Field(default="1:1", description="Aspect ratio for generated images")
    negative_prompt: Optional[str] = Field(default="", description="Negative prompt to avoid certain elements")
    person_generation: str = Field(default="allow_all", description="Person generation policy")
    safety_filter_level: str = Field(default="block_few", description="Safety filter level")
    add_watermark: bool = Field(default=True, description="Add watermark to generated images")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "prompt": "hoa anh đào nở rộ",
                    "number_of_images": 1,
                    "aspect_ratio": "1:1",
                    "negative_prompt": "",
                    "person_generation": "allow_all",
                    "safety_filter_level": "block_few",
                    "add_watermark": True

                }
            ]
        }


class ImageGenerationResponse(BaseModel):
    success: bool
    message: str
    images: List[str] = Field(default_factory=list, description="Base64 encoded images")
    generation_time: float
    timestamp: str
