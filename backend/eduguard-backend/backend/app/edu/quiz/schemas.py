"""Quiz data model.

Field names follow the EduGuard frontend (src/types/eduguard.ts as used in App.tsx):
QuizQuestion.{id, code, number, bloom, stem, options[{key,text}], explanation, baseMetrics,
source, fixes[{id, targetField, suggestedReplacement, fixed}]}. Extra fields (images, tables,
type, correctKey...) are additive, so the current UI keeps working.
If your eduguard.ts uses different keys for baseMetrics/source, adjust `to_frontend()` only.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.edu.docparse.models import DocImage, DocTable

QuestionType = Literal["mcq", "true_false", "short_answer"]
Bloom = Literal["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"]


class CamelModel(BaseModel):
    """Accept snake_case or camelCase in, emit camelCase out (by_alias=True)."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class QuizOption(CamelModel):
    key: str                                   # "A".."H" (mcq) or "a".."d" (true_false)
    text: str
    image_ids: List[str] = Field(default_factory=list)
    is_correct: Optional[bool] = None          # true_false: truth value of the statement
    misconception: Optional[str] = None        # distractor: the misunderstanding it targets


class SourceRef(CamelModel):
    doc_id: Optional[str] = None
    chunk_id: Optional[str] = None
    heading_path: List[str] = Field(default_factory=list)
    quote: str = ""                            # passage shown in the grounding panel
    page: Optional[int] = None
    image_ids: List[str] = Field(default_factory=list)
    score: Optional[float] = None


class Fix(CamelModel):
    id: str
    kind: str                                  # answer_ungrounded | distractor_also_correct | answer_leak | ...
    severity: Literal["error", "warning", "info"] = "warning"
    message: str
    target_field: str                          # stem | explanation | optionA..optionD | correctKey
    suggested_replacement: str = ""
    evidence_chunk_id: Optional[str] = None
    fixed: bool = False


class QuizQuestion(CamelModel):
    id: str
    code: str
    number: int
    type: QuestionType = "mcq"
    section: Optional[str] = None
    bloom: Optional[str] = None
    stem: str
    stem_image_ids: List[str] = Field(default_factory=list)
    stem_table_ids: List[str] = Field(default_factory=list)
    options: List[QuizOption] = Field(default_factory=list)
    correct_key: Optional[str] = None
    answer_text: Optional[str] = None          # short_answer
    explanation: str = ""
    answer_detected_by: Optional[str] = None   # key_table | inline | underline | color | highlight | bold | llm
    source: SourceRef = Field(default_factory=SourceRef)
    base_metrics: Dict[str, int] = Field(default_factory=dict)
    fixes: List[Fix] = Field(default_factory=list)
    origin: Literal["extracted", "generated"] = "extracted"
    depth: Optional[str] = None                # co_ban | tinh_huong | nhieu_buoc | doc_bang | doc_hinh
    source_chunk_ids: List[str] = Field(default_factory=list)
    verdict: Optional[Dict] = None             # KHOP/SAI/THIEU label from app/edu/verify (per-option check)
    decision: Literal["chua_quyet", "chap_nhan", "tu_choi_cau", "da_sua"] = "chua_quyet"


class QuizSet(CamelModel):
    id: str
    doc_id: str
    title: str
    engine: str
    questions: List[QuizQuestion]
    images: Dict[str, DocImage] = Field(default_factory=dict)
    tables: Dict[str, DocTable] = Field(default_factory=dict)
    original: Dict[str, QuizQuestion] = Field(default_factory=dict)  # snapshot for Undo
    warnings: List[str] = Field(default_factory=list)
    status: Literal["nhap", "cho_duyet"] = "nhap"   # no "published" state: a teacher publishes outside


class GenerateQuizRequest(CamelModel):
    num_questions: int = Field(10, ge=1, le=60)
    bloom_mix: Dict[str, int] = Field(default_factory=lambda: {"Nhận biết": 40, "Thông hiểu": 30, "Vận dụng": 20, "Vận dụng cao": 10})
    question_types: List[QuestionType] = Field(default_factory=lambda: ["mcq"])
    language: str = "Vietnamese"
    engine: Optional[str] = None               # override settings.QUIZ_ENGINE
    include_images: bool = True                # send figures to a multimodal model
    title: Optional[str] = None
    depth: bool = True                         # scenario / multi-step / table-figure questions + misconceptions
    verify: bool = True                        # label every generated question with app/edu/verify


class QuestionDecisionRequest(CamelModel):
    action: Literal["accept", "reject", "reset"]


class EvaluateRequest(CamelModel):
    use_llm: bool = True
    question_ids: Optional[List[str]] = None


class UpdateQuestionRequest(CamelModel):
    stem: Optional[str] = None
    explanation: Optional[str] = None
    correct_key: Optional[str] = None
    bloom: Optional[str] = None
    options: Optional[List[QuizOption]] = None
