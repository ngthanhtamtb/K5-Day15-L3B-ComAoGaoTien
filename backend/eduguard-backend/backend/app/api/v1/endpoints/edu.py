"""EduGuard endpoints: document parsing, quiz (extract / generate / eval / fix), slides + voice.

Mounted at /api/v1/edu (see app/api/v1/api.py). These routes don't require login so the
EduGuard frontend works out of the box, except the presentation route which touches
RAGslides' per-user presentations and therefore uses get_current_user.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.llm import collect
from app.edu.billing import PlanContext, plan_context
from app.core.database import get_db
from app.edu import docparse
from app.edu.quiz import service as quiz_service
from app.edu.quiz.schemas import EvaluateRequest, GenerateQuizRequest, UpdateQuestionRequest
from app.edu.tts import get_provider
from app.edu.voice import service as voice_service
from app.models.user import User

router = APIRouter()


def _nf(e: Exception):
    raise HTTPException(status_code=404, detail=str(e))


# =========================================================================== documents
@router.post("/documents", summary="Upload & parse a document (docx/pdf/pptx/doc/md) keeping images, tables, layout")
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > settings.EDU_MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.EDU_MAX_UPLOAD_MB} MB")
    try:
        doc = await docparse.ingest(data, file.filename or "upload.docx")
    except docparse.UnsupportedDocument as e:
        raise HTTPException(400, str(e))
    return {
        "docId": doc.doc_id, "filename": doc.filename, "engine": doc.engine,
        "stats": {"blocks": len(doc.blocks), "images": len(doc.images), "tables": len(doc.tables),
                  "chunks": len(doc.chunks)},
        "markdown": doc.markdown,
    }


@router.get("/documents/{doc_id}", summary="Full parsed document (blocks, images, tables, chunks)")
async def get_document(doc_id: str, include_blocks: bool = True):
    try:
        doc = docparse.load(doc_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not doc:
        raise HTTPException(404, "document not found")
    return doc.model_dump(exclude={"blocks"} if not include_blocks else None)


@router.get("/documents/{doc_id}/search", summary="BM25 search over chunks (source grounding)")
async def search_document(doc_id: str, q: str, k: int = 5):
    from app.edu.retrieval import ChunkRetriever
    doc = docparse.load(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return [{"chunk": c.model_dump(), "score": round(s, 3)} for c, s in ChunkRetriever(doc.chunks).search(q, k)]


# =========================================================================== quizzes
def _out(obj):
    return obj.model_dump(by_alias=True)


@router.post("/documents/{doc_id}/quiz/extract", summary="Extract existing questions from an exam file")
async def extract_quiz(doc_id: str):
    try:
        return _out(quiz_service.extract(doc_id))
    except quiz_service.NotFound as e:
        _nf(e)


@router.post("/documents/{doc_id}/quiz/generate", summary="Generate questions (LLM router or BE_Zentus) + per-question source check")
async def generate_quiz(doc_id: str, req: GenerateQuizRequest, ctx: PlanContext = Depends(plan_context)):
    if req.depth:
        ctx.require("quiz_depth")
    for t in req.question_types:
        ctx.require("quiz_types", t)
    ctx.consume("quiz_questions", req.num_questions)
    try:
        with collect() as trace:
            qs = await quiz_service.generate(doc_id, req, plan=ctx.feature("llm_route") or ctx.plan_id)
        return {**_out(qs), "trace": trace.summary(), "quotaWarnings": ctx.warnings}
    except quiz_service.NotFound as e:
        _nf(e)
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str):
    try:
        return _out(quiz_service.get(quiz_id))
    except (quiz_service.NotFound, ValueError) as e:
        _nf(e)


@router.post("/quizzes/{quiz_id}/evaluate", summary="Eval: grounding, distractors, leakage → baseMetrics + fixes")
async def evaluate_quiz(quiz_id: str, req: EvaluateRequest = EvaluateRequest()):
    try:
        return _out(await quiz_service.evaluate(quiz_id, req))
    except quiz_service.NotFound as e:
        _nf(e)


@router.patch("/quizzes/{quiz_id}/questions/{question_id}", summary="Teacher edits a question")
async def update_question(quiz_id: str, question_id: str, req: UpdateQuestionRequest):
    try:
        return _out(quiz_service.update_question(quiz_id, question_id, req))
    except quiz_service.NotFound as e:
        _nf(e)


@router.post("/quizzes/{quiz_id}/questions/{question_id}/fixes/{fix_id}/apply")
async def apply_fix(quiz_id: str, question_id: str, fix_id: str):
    try:
        return _out(quiz_service.apply_fix(quiz_id, question_id, fix_id))
    except quiz_service.NotFound as e:
        _nf(e)


@router.post("/quizzes/{quiz_id}/questions/{question_id}/fixes/{fix_id}/undo")
async def undo_fix(quiz_id: str, question_id: str, fix_id: str):
    try:
        return _out(quiz_service.apply_fix(quiz_id, question_id, fix_id, undo=True))
    except quiz_service.NotFound as e:
        _nf(e)


# =========================================================================== voice
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=2.0)


class SlidesScriptRequest(BaseModel):
    slides: List[Dict[str, Any]]             # PPTist slides
    lesson_title: str = ""
    language: str = "Vietnamese"
    style: str = "thân thiện, rõ ràng"
    words_per_slide: int = Field(90, ge=20, le=400)
    overwrite: bool = False
    doc_id: Optional[str] = None             # ground scripts in the source document


class SlidesVoiceRequest(BaseModel):
    slides: List[Dict[str, Any]]
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=2.0)
    embed_audio_element: bool = True         # add a PPTist audio element (autoplay) to each slide
    width: float = 1000
    height: float = 562.5


class PresentationVoiceRequest(BaseModel):
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=2.0)
    write_missing_scripts: bool = True
    language: str = "Vietnamese"


@router.get("/voice/voices")
async def list_voices():
    p = get_provider()
    return {"provider": p.name, "voices": await p.list_voices()}


@router.post("/voice/synthesize", summary="Text → audio file (cached)")
async def synthesize(req: SynthesizeRequest):
    try:
        return await voice_service.synthesize(req.text, req.voice, req.speed)
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")


@router.post("/slides/scripts", summary="Write speaker scripts (slide.remark) for slides that have none")
async def slides_scripts(req: SlidesScriptRequest):
    try:
        slides = await voice_service.ensure_scripts(req.slides, req.lesson_title, req.language, req.style,
                                                    req.words_per_slide, req.overwrite, req.doc_id)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"slides": slides}


@router.post("/slides/voice", summary="TTS each slide's remark and attach audio (PPTist JSON in/out)")
async def slides_voice(req: SlidesVoiceRequest):
    try:
        return await voice_service.voice_slides(req.slides, req.voice, req.speed, req.embed_audio_element,
                                                req.width, req.height)
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")


@router.post("/presentations/{presentation_id}/voice",
             summary="Voice a stored RAGslides presentation (writes audio into page_data)")
async def presentation_voice(presentation_id: str, req: PresentationVoiceRequest,
                             current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return await voice_service.voice_presentation(db, presentation_id, current_user.id, req.voice, req.speed,
                                                      req.write_missing_scripts, req.language)
    except LookupError as e:
        _nf(e)
    except PermissionError as e:
        raise HTTPException(403, str(e))
