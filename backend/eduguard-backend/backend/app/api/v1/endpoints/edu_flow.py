"""EduGuard review flow (mounted at /api/v1/edu, next to edu.py):

  documents (async ingest job) · verify · scripts (gate 1) · slides from script · voice
  (estimate / job / per-segment timeline) · quiz gates · jobs (+SSE) · plans · LLM status

Every response that ran a model carries `trace` (steps, model calls, tokens, cost) for the
"Agent verify" panel. Login is optional: anonymous users get the default plan.
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.jobs import jobs
from app.core.llm import collect, llm
from app.edu import docparse
from app.edu.billing import PlanContext, load_plans, plan_context
from app.edu.quiz import service as quiz_service
from app.edu.quiz.schemas import QuestionDecisionRequest
from app.edu.scripts import service as scripts
from app.edu.scripts.models import CreateScriptRequest, DecisionsRequest
from app.edu.verify import check_items

router = APIRouter()


def _route(ctx: PlanContext) -> Optional[str]:
    return ctx.feature("llm_route") or ctx.plan_id


def _http(e: Exception):
    if isinstance(e, (scripts.NotFound, quiz_service.NotFound, FileNotFoundError, LookupError)):
        raise HTTPException(404, str(e))
    if isinstance(e, (scripts.Conflict, quiz_service.Conflict)):
        raise HTTPException(409, str(e))
    if isinstance(e, (scripts.Invalid, ValueError)):
        raise HTTPException(422, str(e))
    raise e


def _with(data, trace=None, ctx: Optional[PlanContext] = None):
    out = {"data": data}
    if trace is not None:
        out["trace"] = trace.summary()
    if ctx is not None and ctx.warnings:
        out["quotaWarnings"] = ctx.warnings
    return out


# =========================================================================== plans / status
@router.get("/plans", summary="Plans and their features/quotas (framework — enforcement off by default)")
async def plans():
    cfg = load_plans()
    return {"enforced": settings.BILLING_ENFORCE, "defaultPlan": cfg.get("default_plan"), "plans": cfg.get("plans")}


@router.get("/me/plan", summary="Current user's plan, role and monthly usage")
async def my_plan(ctx: PlanContext = Depends(plan_context)):
    return ctx.summary()


@router.get("/llm/status", summary="Which providers have credentials and how each task is routed")
async def llm_status():
    return {"providers": llm.available(), "routes": llm.routes, "pricedModels": sorted(llm.pricing)}


# =========================================================================== documents (async)
@router.post("/documents/async", summary="Upload + parse as a background job (large PDFs, OCR)")
async def upload_document_async(file: UploadFile = File(...), ctx: PlanContext = Depends(plan_context)):
    data = await file.read()
    if len(data) > settings.EDU_MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.EDU_MAX_UPLOAD_MB} MB")
    if settings.EDU_OCR_ENABLED:
        ctx.require("ocr")
    ctx.consume("documents", 1)
    name = file.filename or "upload"

    async def run(job):
        job.progress(5, "Đang đọc tài liệu")
        with collect() as trace:
            doc = await docparse.ingest(data, name)
        job.progress(95, "Đã tách đoạn")
        return {"docId": doc.doc_id, "engine": doc.engine, "meta": doc.meta,
                "stats": {"blocks": len(doc.blocks), "images": len(doc.images), "tables": len(doc.tables),
                          "chunks": len(doc.chunks)}, "trace": trace.summary()}

    job = jobs.submit("ingest", run, owner=ctx.uid, meta={"filename": name})
    return {"jobId": job.id, "status": job.status, "quotaWarnings": ctx.warnings}


@router.get("/documents/{doc_id}/pages/{page}", summary="Blocks of one page with bbox (to highlight a cited source)")
async def document_page(doc_id: str, page: int):
    doc = docparse.load(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    blocks = [b.model_dump() for b in doc.blocks if b.page == page]
    images = [i.model_dump() for i in doc.images.values() if i.page == page]
    return {"docId": doc_id, "page": page, "blocks": blocks, "images": images}


# =========================================================================== verify
class VerifyBody(BaseModel):
    doc_id: str
    items: List[str] = Field(..., min_length=1, max_length=200)
    need_fix: bool = False


@router.post("/verify", summary="Label statements KHOP_NGUON / SAI_NGUON / THIEU_NGUON / TU_CHOI against a document")
async def verify(body: VerifyBody, ctx: PlanContext = Depends(plan_context)):
    doc = docparse.load(body.doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    with collect() as trace:
        res = await check_items(doc, body.items, need_fix=body.need_fix, plan=_route(ctx))
    return _with(res, trace, ctx)


# =========================================================================== scripts (gate 1)
def _script_out(sc):
    return {**sc.model_dump(by_alias=True), "counts": scripts.counts(sc)}


@router.post("/scripts", summary="Create a script: paste (noiDung) or generate from the document (chuDe)")
async def create_script(req: CreateScriptRequest, ctx: PlanContext = Depends(plan_context)):
    try:
        with collect() as trace:
            sc = await scripts.create(req, plan=_route(ctx), owner=ctx.user_key)
        sc.trace = trace.summary()
        scripts.save(sc)
    except Exception as e:
        _http(e)
    return _with(_script_out(sc), trace, ctx)


@router.get("/scripts/{script_id}")
async def get_script(script_id: str):
    try:
        return {"data": _script_out(scripts.get(script_id))}
    except Exception as e:
        _http(e)


@router.post("/scripts/{script_id}/decisions", summary="Accept / reject / edit (re-checked) / reset segments")
async def script_decisions(script_id: str, req: DecisionsRequest, ctx: PlanContext = Depends(plan_context)):
    try:
        with collect() as trace:
            sc = await scripts.decide(script_id, req, plan=_route(ctx))
    except Exception as e:
        _http(e)
    return _with(_script_out(sc), trace, ctx)


@router.post("/scripts/{script_id}/accept-matching", summary="Accept every undecided KHOP_NGUON segment")
async def script_accept_matching(script_id: str):
    try:
        return {"data": _script_out(scripts.accept_matching(script_id))}
    except Exception as e:
        _http(e)


@router.post("/scripts/{script_id}/submit", summary="Gate 1 done -> status cho_duyet (409 if undecided segments)")
async def script_submit(script_id: str):
    try:
        return {"data": _script_out(scripts.submit(script_id))}
    except Exception as e:
        _http(e)


class ReviseBody(BaseModel):
    slide: int
    segment: str
    text: str = Field(..., min_length=1, max_length=4000)


@router.post("/scripts/{script_id}/revise", summary="Gate 2: edit a segment after submit -> re-checked, suggestion with source")
async def script_revise(script_id: str, body: ReviseBody, ctx: PlanContext = Depends(plan_context)):
    try:
        with collect() as trace:
            sc = await scripts.revise(script_id, body.slide, body.segment, body.text, plan=_route(ctx))
    except Exception as e:
        _http(e)
    return _with(_script_out(sc), trace, ctx)


@router.get("/scripts", summary="List scripts (library)")
async def list_scripts():
    return {"data": scripts.list_scripts()}


@router.get("/documents", summary="List uploaded documents (library)")
async def list_documents():
    from app.edu.docparse.service import list_documents as _ls
    return {"data": _ls()}


@router.get("/quizzes", summary="List quizzes (library)")
async def list_quizzes():
    return {"data": quiz_service.list_quizzes()}


@router.get("/quizzes/{quiz_id}/pdf", summary="Structured PDF: exam paper (answers=false) or answer key (answers=true)")
async def quiz_pdf(quiz_id: str, answers: bool = False):
    from fastapi.responses import Response
    from app.edu.quiz_pdf import render
    try:
        qs = quiz_service.get(quiz_id)
        data = render(qs, answers=answers)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        _http(e)
    name = f"{quiz_id}-{'dap-an' if answers else 'de'}.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


# =========================================================================== slides from script
@router.get("/templates", summary="Slide templates available for script -> slides")
async def templates():
    from app.edu.slides_builder import list_templates
    return {"data": list_templates()}


class BuildSlidesBody(BaseModel):
    template: str = "template_1"


@router.post("/scripts/{script_id}/slides", summary="Approved script -> PPTist slides (source figures, labels, audio)")
async def script_slides(script_id: str, body: BuildSlidesBody = BuildSlidesBody()):
    from app.edu.slides_builder import build_slides
    try:
        sc = scripts.get(script_id)
        if sc.status != "cho_duyet":
            raise scripts.Conflict("kịch bản chưa qua cổng 1 (status phải là cho_duyet)")
        return {"data": await build_slides(sc, body.template)}
    except Exception as e:
        _http(e)


# =========================================================================== voice
class VoiceBody(BaseModel):
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=2.0)


@router.post("/scripts/{script_id}/voice/estimate", summary="Characters, requests, audio length and cost BEFORE generating")
async def script_voice_estimate(script_id: str, body: VoiceBody = VoiceBody(), ctx: PlanContext = Depends(plan_context)):
    from app.edu.voice.script_voice import estimate_script
    try:
        est = estimate_script(scripts.get(script_id), body.voice, body.speed)
    except Exception as e:
        _http(e)
    limit = (ctx.plan.get("quotas") or {}).get("voice_chars")
    est["quota"] = {"used": ctx.used("voice_chars"), "limit": limit, "enforced": ctx.enforced}
    return {"data": est}


@router.post("/scripts/{script_id}/voice", summary="Voice the approved script as a background job (poll /jobs/{id})")
async def script_voice(script_id: str, body: VoiceBody = VoiceBody(), ctx: PlanContext = Depends(plan_context)):
    from app.edu.voice.script_voice import voice_script
    ctx.require("voice")
    try:
        sc = scripts.get(script_id)
        if sc.status != "cho_duyet":
            raise scripts.Conflict("chỉ sinh giọng cho kịch bản đã qua cổng 1 (status = cho_duyet)")
    except Exception as e:
        _http(e)

    async def run(job):
        bg = ctx.for_background()
        try:
            return await voice_script(script_id, body.voice, body.speed, job=job, plan_ctx=bg)
        finally:
            bg.db.close()

    job = jobs.submit("voice", run, owner=ctx.uid, meta={"scriptId": script_id})
    return {"jobId": job.id, "status": job.status, "quotaWarnings": ctx.warnings}


# =========================================================================== quiz gates
@router.post("/quizzes/{quiz_id}/questions/{question_id}/decision", summary="Gate decision for one question")
async def quiz_decision(quiz_id: str, question_id: str, req: QuestionDecisionRequest):
    try:
        return {"data": quiz_service.decide(quiz_id, question_id, req.action).model_dump(by_alias=True)}
    except Exception as e:
        _http(e)


@router.post("/quizzes/{quiz_id}/questions/{question_id}/verify", summary="Gate 2: re-check an edited question")
async def quiz_reverify(quiz_id: str, question_id: str, ctx: PlanContext = Depends(plan_context)):
    try:
        with collect() as trace:
            q = await quiz_service.reverify(quiz_id, question_id, plan=_route(ctx))
    except Exception as e:
        _http(e)
    return _with(q.model_dump(by_alias=True), trace, ctx)


@router.post("/quizzes/{quiz_id}/submit", summary="All questions decided -> status cho_duyet")
async def quiz_submit(quiz_id: str):
    try:
        return {"data": quiz_service.submit(quiz_id).model_dump(by_alias=True)}
    except Exception as e:
        _http(e)


# =========================================================================== jobs
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.snapshot()


@router.get("/jobs/{job_id}/events", summary="Server-sent events with job progress until it finishes")
async def job_events(job_id: str):
    from sse_starlette.sse import EventSourceResponse
    if not jobs.get(job_id):
        raise HTTPException(404, "job not found")

    async def stream():
        async for snap in jobs.events(job_id):
            yield {"event": snap["status"], "data": json.dumps(snap, ensure_ascii=False, default=str)}

    return EventSourceResponse(stream())


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    return {"cancelled": jobs.cancel(job_id)}
