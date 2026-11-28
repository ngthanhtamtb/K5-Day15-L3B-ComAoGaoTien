from __future__ import annotations

from typing import List, Optional

from app.edu import storage
from app.edu.docparse import load as load_doc
from app.edu.docparse.models import ParsedDocument
from .engines import get_engine
from .evaluator import evaluate_question
from .extractor import extract_questions
from .schemas import EvaluateRequest, GenerateQuizRequest, QuizQuestion, QuizSet, UpdateQuestionRequest


class NotFound(LookupError):
    pass


def _doc(doc_id: str) -> ParsedDocument:
    doc = load_doc(doc_id)
    if not doc:
        raise NotFound(f"document {doc_id} not found")
    return doc


def _media_subset(doc: ParsedDocument, questions: List[QuizQuestion]):
    img_ids, tbl_ids = set(), set()
    for q in questions:
        img_ids.update(q.stem_image_ids)
        img_ids.update(q.source.image_ids)
        tbl_ids.update(q.stem_table_ids)
        for o in q.options:
            img_ids.update(o.image_ids)
    for t in tbl_ids:
        tb = doc.tables.get(t)
        if tb:
            for c in tb.cells:
                for b in c.blocks:
                    img_ids.update(b.image_ids)
    return ({i: doc.images[i] for i in img_ids if i in doc.images},
            {t: doc.tables[t] for t in tbl_ids if t in doc.tables})


def save(qs: QuizSet) -> QuizSet:
    storage.save_json(qs.model_dump(), "quizzes", f"{qs.id}.json")
    return qs


def get(quiz_id: str) -> QuizSet:
    data = storage.load_json("quizzes", f"{storage.check_id(quiz_id)}.json")
    if not data:
        raise NotFound(f"quiz {quiz_id} not found")
    return QuizSet(**data)


def _finish(doc: ParsedDocument, questions: List[QuizQuestion], engine: str, title: str,
            warnings: Optional[List[str]] = None) -> QuizSet:
    images, tables = _media_subset(doc, questions)
    qs = QuizSet(id=storage.new_id("quiz"), doc_id=doc.doc_id, title=title, engine=engine,
                 questions=questions, images=images, tables=tables,
                 original={q.id: q for q in questions}, warnings=warnings or [])
    return save(qs)


def extract(doc_id: str) -> QuizSet:
    doc = _doc(doc_id)
    questions, warnings = extract_questions(doc)
    if not questions:
        warnings.append("Không tìm thấy câu hỏi dạng 'Câu N.' trong tài liệu.")
    return _finish(doc, questions, "extractor", doc.filename, warnings)


async def generate(doc_id: str, req: GenerateQuizRequest, plan: Optional[str] = None) -> QuizSet:
    doc = _doc(doc_id)
    engine = get_engine(req.engine, plan=plan)
    questions = await engine.generate(doc, req)
    if req.verify:
        await verify_questions(doc, questions, plan)
    return _finish(doc, questions, engine.name, req.title or f"Quiz · {doc.filename}")


async def verify_questions(doc: ParsedDocument, questions: List[QuizQuestion], plan: Optional[str] = None) -> None:
    """Gate-1 label per question: checks EVERY option against the source (catches 2 correct answers)."""
    from app.edu.verify import check_items
    from app.edu.verify.service import quiz_as_text
    mcq = [q for q in questions if q.type == "mcq"]
    if not mcq:
        return
    results = await check_items(doc, [quiz_as_text(q) for q in mcq], quiz=True, need_fix=True, plan=plan)
    for q, r in zip(mcq, results):
        q.verdict = r


async def reverify(quiz_id: str, question_id: str, plan: Optional[str] = None) -> QuizQuestion:
    """Gate 2: re-check one question after the teacher edited it."""
    qs = get(quiz_id)
    doc = _doc(qs.doc_id)
    q = next((x for x in qs.questions if x.id == question_id), None)
    if q is None:
        raise NotFound(question_id)
    await verify_questions(doc, [q], plan)
    save(qs)
    return q


class Conflict(RuntimeError):
    pass


def decide(quiz_id: str, question_id: str, action: str) -> QuizQuestion:
    qs = get(quiz_id)
    q = next((x for x in qs.questions if x.id == question_id), None)
    if q is None:
        raise NotFound(question_id)
    q.decision = {"accept": "chap_nhan", "reject": "tu_choi_cau", "reset": "chua_quyet"}[action]
    save(qs)
    return q


def list_quizzes() -> List[dict]:
    import os
    root = os.path.join(storage.edu_root(), "quizzes")
    out = []
    for name in os.listdir(root) if os.path.isdir(root) else []:
        if not name.endswith(".json"):
            continue
        p = os.path.join(root, name)
        data = storage.load_json("quizzes", name)
        if not data:
            continue
        qs = QuizSet(**data)
        out.append({"id": qs.id, "docId": qs.doc_id, "title": qs.title, "engine": qs.engine, "status": qs.status,
                    "questions": len(qs.questions), "updatedAt": os.path.getmtime(p),
                    "decided": sum(1 for q in qs.questions if q.decision != "chua_quyet"),
                    "needsReview": sum(1 for q in qs.questions if (q.verdict or {}).get("nhan") in ("SAI_NGUON", "THIEU_NGUON")
                                       and q.decision not in ("chap_nhan", "tu_choi_cau"))})
    return sorted(out, key=lambda s: -s["updatedAt"])




async def evaluate(quiz_id: str, req: EvaluateRequest) -> QuizSet:
    qs = get(quiz_id)
    doc = load_doc(qs.doc_id)
    engine = None
    if req.use_llm:
        try:
            engine = get_engine()
        except Exception:
            engine = None  # no API key configured -> deterministic checks only
    targets = set(req.question_ids or [q.id for q in qs.questions])
    import asyncio
    sem = asyncio.Semaphore(4)

    async def one(q: QuizQuestion) -> QuizQuestion:
        if q.id not in targets:
            return q
        async with sem:
            return await evaluate_question(q, doc, engine, req.use_llm)

    qs.questions = list(await asyncio.gather(*(one(q) for q in qs.questions)))
    if doc:
        images, tables = _media_subset(doc, qs.questions)
        qs.images.update(images)
        qs.tables.update(tables)
    return save(qs)


def update_question(quiz_id: str, question_id: str, req: UpdateQuestionRequest) -> QuizQuestion:
    qs = get(quiz_id)
    for i, q in enumerate(qs.questions):
        if q.id == question_id:
            patch = req.model_dump(exclude_none=True)
            q = q.model_copy(update={**patch, "decision": "da_sua", "verdict": None})  # needs re-verify
            if q.correct_key:
                for o in q.options:
                    if q.type == "mcq":
                        o.is_correct = o.key == q.correct_key
            qs.questions[i] = q
            save(qs)
            return q
    raise NotFound(question_id)


def _set_field(q: QuizQuestion, field: str, value: str) -> QuizQuestion:
    if field == "stem":
        q.stem = value
    elif field == "explanation":
        q.explanation = value
    elif field == "correctKey":
        key = value.strip()[:1].upper()
        q.correct_key = key
        for o in q.options:
            o.is_correct = o.key == key
    elif field.startswith("option"):
        key = field.replace("option", "")
        for o in q.options:
            if o.key == key:
                o.text = value
    return q


def apply_fix(quiz_id: str, question_id: str, fix_id: str, undo: bool = False) -> QuizQuestion:
    qs = get(quiz_id)
    for i, q in enumerate(qs.questions):
        if q.id != question_id:
            continue
        fix = next((f for f in q.fixes if f.id == fix_id), None)
        if not fix:
            raise NotFound(fix_id)
        if undo:
            orig = qs.original.get(q.id)
            if orig:
                field = fix.target_field
                if field == "correctKey":
                    value = orig.correct_key or ""
                elif field.startswith("option"):
                    value = next((o.text for o in orig.options if o.key == field.replace("option", "")), "")
                else:
                    value = getattr(orig, field, "")
                q = _set_field(q, field, value)
            fix.fixed = False
        else:
            if fix.suggested_replacement:
                q = _set_field(q, fix.target_field, fix.suggested_replacement)
            fix.fixed = True
        qs.questions[i] = q
        save(qs)
        return q
    raise NotFound(question_id)
