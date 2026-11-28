"""Eval for quiz questions -> baseMetrics, source grounding and suggested fixes.

Two layers:
  1. Deterministic checks (free, instant, explainable): missing answer, duplicate options,
     answer leak by length / keyword echo, "all of the above", unemphasised negation,
     weak retrieval support.
  2. Engine review (Gemini or BE_Zentus evaluate fn): is the key grounded, is a distractor
     also correct, ambiguity, Bloom level — each issue comes with a full replacement text
     so the UI's "Áp dụng sửa" button can apply it.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Dict, List, Optional

from app.edu.docparse.models import ParsedDocument
from app.edu.retrieval import ChunkRetriever
from app.edu.retrieval.bm25 import tokenize
from .engines import QuizEngine
from .schemas import Fix, QuizQuestion, SourceRef

logger = logging.getLogger(__name__)

NEGATION = re.compile(r"\b(không|chưa|ngoại trừ|trừ)\b", re.I)
ALL_ABOVE = re.compile(r"(tất cả|cả\s+[a-d]\s*,|đều đúng|đều sai|all of the above|none of the above)", re.I)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s or "").strip().lower())


def deterministic_checks(q: QuizQuestion) -> List[Fix]:
    fixes: List[Fix] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        fixes.append(Fix(id=f"{q.id}-d{n}", **kw))

    if q.type == "mcq":
        if not q.correct_key:
            add(kind="missing_answer", severity="error", target_field="correctKey",
                message="Chưa xác định được đáp án đúng.")
        texts = [_norm(o.text) for o in q.options if o.text]
        if len(set(texts)) < len(texts):
            add(kind="duplicate_options", severity="error", target_field="stem",
                message="Có hai phương án trùng nội dung.")
        correct = next((o for o in q.options if o.key == q.correct_key), None)
        others = [o for o in q.options if o.key != q.correct_key and o.text]
        if correct and correct.text and others:
            avg = sum(len(o.text) for o in others) / len(others)
            if len(correct.text) > 1.6 * avg and len(correct.text) - avg > 15:
                add(kind="answer_leak", severity="warning", target_field=f"option{correct.key}",
                    message="Đáp án đúng dài hơn hẳn các phương án nhiễu — học sinh dễ đoán.")
            stem_toks = set(tokenize(q.stem)) - set(tokenize("là của và các những được có trong một"))
            echo = [t for t in tokenize(correct.text) if "_" in t and t in stem_toks]
            echo_others = [o for o in others if any("_" in t and t in stem_toks for t in tokenize(o.text))]
            if echo and not echo_others:
                add(kind="answer_leak", severity="warning", target_field=f"option{correct.key}",
                    message=f"Chỉ đáp án đúng lặp lại cụm từ của câu hỏi (\"{echo[0].replace('_', ' ')}\").")
        for o in q.options:
            if ALL_ABOVE.search(o.text):
                add(kind="all_of_above", severity="info", target_field=f"option{o.key}",
                    message="Tránh phương án kiểu \"tất cả đều đúng/sai\".")
    m = NEGATION.search(q.stem)
    if m and m.group(0) != m.group(0).upper():
        word = m.group(0)
        add(kind="negation_not_emphasised", severity="info", target_field="stem",
            message=f"Câu hỏi phủ định — nên in hoa \"{word.upper()}\" để học sinh không đọc sót.",
            suggested_replacement=q.stem[:m.start()] + word.upper() + q.stem[m.end():])
    if not q.stem.strip() and not q.stem_image_ids:
        add(kind="empty_stem", severity="error", target_field="stem", message="Câu hỏi trống.")
    return fixes


def _query_text(q: QuizQuestion) -> str:
    correct = next((o.text for o in q.options if o.key == q.correct_key), "")
    return " ".join([q.stem, correct, q.answer_text or ""])


async def evaluate_question(q: QuizQuestion, source_doc: Optional[ParsedDocument],
                            engine: Optional[QuizEngine], use_llm: bool = True) -> QuizQuestion:
    q = q.model_copy(deep=True)
    fixed_before = {f.kind: f.fixed for f in q.fixes}
    fixes = deterministic_checks(q)
    metrics: Dict[str, int] = {"grounding": 0, "distractors": 70, "clarity": 80, "leakage": 90}

    evidence = []
    if source_doc and source_doc.chunks:
        retriever = ChunkRetriever(source_doc.chunks)
        hits = retriever.search(_query_text(q), k=3)
        if q.source.chunk_id and retriever.get(q.source.chunk_id):
            pinned = retriever.get(q.source.chunk_id)
            hits = [(pinned, hits[0][1] if hits else 1.0)] + [h for h in hits if h[0].id != pinned.id][:2]
        evidence = [c for c, _ in hits]
        if hits:
            best, score = hits[0]
            q.source = SourceRef(doc_id=source_doc.doc_id, chunk_id=best.id, heading_path=best.heading_path,
                                 quote=q.source.quote or best.text[:500], image_ids=best.image_ids,
                                 page=q.source.page, score=round(score, 2))
            # BM25 → rough 0..100 support signal, refined by the LLM below
            metrics["grounding"] = int(min(100, 25 + score * 6))
        else:
            fixes.append(Fix(id=f"{q.id}-g0", kind="answer_ungrounded", severity="warning", target_field="correctKey",
                             message="Không tìm thấy đoạn nào trong tài liệu nguồn chứa nội dung đáp án."))

    if any(f.kind == "answer_leak" for f in fixes):
        metrics["leakage"] = 55
    if any(f.kind in ("duplicate_options", "all_of_above") for f in fixes):
        metrics["distractors"] = 50
    if any(f.kind == "negation_not_emphasised" for f in fixes):
        metrics["clarity"] = 70

    if use_llm and engine is not None:
        try:
            review = await engine.review(q, evidence)
        except Exception as e:  # LLM failure must not break the review screen
            logger.warning("LLM review failed for %s: %s", q.id, e)
            review = None
        if review:
            for k, v in (review.get("metrics") or {}).items():
                try:
                    metrics[k] = int(v)
                except (TypeError, ValueError):
                    pass
            if review.get("bloom") and not q.bloom:
                q.bloom = review["bloom"]
            ev_id = review.get("evidence_chunk_id")
            for i, issue in enumerate(review.get("issues") or []):
                fixes.append(Fix(
                    id=f"{q.id}-l{i + 1}", kind=issue.get("kind", "issue"),
                    severity=issue.get("severity", "warning") if issue.get("severity") in ("error", "warning", "info") else "warning",
                    message=issue.get("message", ""), target_field=issue.get("target_field", "stem"),
                    suggested_replacement=issue.get("suggested_replacement", ""),
                    evidence_chunk_id=ev_id))

    for f in fixes:  # keep "applied" state when re-evaluating
        if fixed_before.get(f.kind):
            f.fixed = True
    q.fixes = fixes
    q.base_metrics = metrics
    return q
