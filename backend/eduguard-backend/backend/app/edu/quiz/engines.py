"""Quiz engines.

QuizEngine is the seam between this backend and whichever core generates questions:
  * ZentusQuizEngine  -> your BE_Zentus quiz core (imported from ZENTUS_PATH)
  * GeminiQuizEngine  -> RAGslides' Gemini client (app/core/pptagent/llm_client.py)
get_engine() picks one from settings and falls back to Gemini if BE_Zentus can't be imported.
"""
from __future__ import annotations

import asyncio
import base64
import importlib
import inspect
import io
import json
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings
from app.edu.docparse.models import Chunk, ParsedDocument
from app.edu.retrieval import ChunkRetriever
from .schemas import Fix, GenerateQuizRequest, QuizOption, QuizQuestion, SourceRef

logger = logging.getLogger(__name__)


class QuizEngine(ABC):
    name = "base"

    @abstractmethod
    async def generate(self, doc: ParsedDocument, req: GenerateQuizRequest) -> List[QuizQuestion]:
        ...

    async def review(self, q: QuizQuestion, evidence: List[Chunk]) -> Optional[dict]:
        """Optional semantic check. Return {"metrics": {...}, "fixes": [...], "bloom": str}."""
        return None


# =========================================================================== helpers
def _json_from_text(text: str) -> Any:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        s, e = text.find(opener), text.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("model did not return JSON")


def normalise_question(raw: Dict[str, Any], idx: int, prefix: str, doc_id: str,
                       retriever: Optional[ChunkRetriever] = None) -> QuizQuestion:
    """Map any reasonable question dict (BE_Zentus, Gemini, ...) onto QuizQuestion."""
    g = lambda *keys, default=None: next((raw[k] for k in keys if k in raw and raw[k] not in (None, "")), default)  # noqa: E731
    stem = g("stem", "question", "content", "text", default="")
    raw_opts = g("options", "choices", "answers", default=[])
    options: List[QuizOption] = []
    if isinstance(raw_opts, dict):
        raw_opts = [{"key": k, "text": v} for k, v in raw_opts.items()]
    for i, o in enumerate(raw_opts or []):
        if isinstance(o, str):
            m = re.match(r"^\s*([A-Ha-h])[.)]\s*(.*)", o)
            options.append(QuizOption(key=m.group(1).upper() if m else chr(65 + i), text=m.group(2) if m else o))
        elif isinstance(o, dict):
            options.append(QuizOption(key=str(o.get("key") or o.get("label") or chr(65 + i)).upper()[:1],
                                      text=str(o.get("text") or o.get("content") or o.get("value") or ""),
                                      image_ids=o.get("image_ids") or o.get("imageIds") or [],
                                      misconception=(o.get("misconception") or None)))
    correct = g("correct_key", "correctKey", "answer", "correct_answer", "correct")
    if isinstance(correct, int) and 0 <= correct < len(options):
        correct = options[correct].key
    if isinstance(correct, str):
        m = re.match(r"^\s*([A-Ha-h])\b", correct)
        if m:
            correct = m.group(1).upper()
        else:  # answer given as the option text
            hit = next((o.key for o in options if o.text.strip().lower() == correct.strip().lower()), None)
            correct = hit
    for o in options:
        o.is_correct = (o.key == correct) if correct else None

    chunk_id = g("source_chunk_id", "chunk_id", "sourceChunkId")
    quote = g("source_quote", "evidence", "quote", default="")
    src = SourceRef(doc_id=doc_id, chunk_id=chunk_id, quote=quote)
    if retriever and chunk_id and retriever.get(chunk_id):
        c = retriever.get(chunk_id)
        src.heading_path, src.image_ids = c.heading_path, c.image_ids
        src.quote = quote or c.text[:400]
    qtype = g("type", default="mcq")
    if qtype not in ("mcq", "true_false", "short_answer"):
        qtype = "mcq" if options else "short_answer"
    chunk_ids = [str(c) for c in (g("source_chunk_ids", "sourceChunkIds", default=[]) or [])]
    if retriever:
        chunk_ids = [c if retriever.get(c) else f"{prefix}-{c}" for c in chunk_ids]
        chunk_ids = [c for c in chunk_ids if retriever.get(c)]          # drop ids the model invented
    if chunk_id and chunk_id not in chunk_ids and (not retriever or retriever.get(chunk_id)):
        chunk_ids.insert(0, chunk_id)
    depth = g("depth")
    return QuizQuestion(
        depth=depth if depth in ("co_ban", "tinh_huong", "nhieu_buoc", "doc_bang", "doc_hinh") else None,
        source_chunk_ids=chunk_ids, stem_table_ids=g("stem_table_ids", default=[]) or [],
        id=f"q{idx:03d}", code=f"{prefix}-Q{idx:02d}", number=idx, type=qtype,
        bloom=g("bloom", "level", "cognitive_level"), stem=str(stem),
        stem_image_ids=g("stem_image_ids", "image_ids", default=[]) or [],
        options=options, correct_key=correct if qtype == "mcq" else None,
        answer_text=g("answer_text") if qtype == "short_answer" else None,
        explanation=str(g("explanation", "rationale", "solution", default="")),
        answer_detected_by="llm", source=src, origin="generated",
    )


def _allocate(n: int, mix: Dict[str, int]) -> Dict[str, int]:
    total = sum(mix.values()) or 1
    alloc = {k: int(n * v / total) for k, v in mix.items()}
    for k in sorted(mix, key=lambda k: -mix[k]):
        if sum(alloc.values()) >= n:
            break
        alloc[k] += 1
    return {k: v for k, v in alloc.items() if v > 0}


# =========================================================================== Gemini (RAGslides core)
GEN_PROMPT = """Bạn là giáo viên ra đề. Chỉ dùng TÀI LIỆU bên dưới (mỗi đoạn có mã [Cxxx]).
Tạo đúng {n} câu hỏi, ngôn ngữ: {language}. Phân bố mức độ Bloom: {alloc}. Loại câu: {types}.

Yêu cầu bắt buộc cho câu trắc nghiệm (mcq):
- 4 phương án A–D, đúng MỘT phương án đúng, có căn cứ trực tiếp trong tài liệu.
- Phương án nhiễu hợp lý nhưng tài liệu loại trừ được; không dùng "tất cả các ý trên".
- Không để lộ đáp án (đáp án không được dài hơn hẳn, không lặp nguyên từ khoá của câu hỏi).
- Nếu câu hỏi dựa vào hình/bảng, ghi mã hình vào "stem_image_ids" (ví dụ ["img003"]).
- "explanation" phải dạy được: nêu nguyên lý làm đáp án đúng, rồi vì sao TỪNG phương án còn lại sai.
Mỗi câu phải trích "source_quote" (≤ 40 từ, chép nguyên văn) và "source_chunk_id".
{depth}
Trả về DUY NHẤT một mảng JSON, mỗi phần tử:
{{"type":"mcq","bloom":"Nhận biết|Thông hiểu|Vận dụng|Vận dụng cao","depth":"co_ban|tinh_huong|nhieu_buoc|doc_bang|doc_hinh",
 "stem":"...","options":[{{"key":"A","text":"...","misconception":"lỗi hiểu sai mà phương án nhiễu này nhắm tới, bỏ trống với đáp án đúng"}},...],
 "correct_key":"B","explanation":"...","source_chunk_id":"C003","source_chunk_ids":["C003"],"source_quote":"...",
 "stem_image_ids":[],"stem_table_ids":[]}}
(true_false: 4 phát biểu a–d trong options, thêm "is_correct" cho từng phát biểu;
 short_answer: bỏ options, thêm "answer_text").

TÀI LIỆU:
{context}
"""

DEPTH_RULES = """
CHIỀU SÂU (bắt buộc với ít nhất một nửa số câu từ mức "Thông hiểu" trở lên):
- tinh_huong: đề mở bằng một tình huống cụ thể (vd "Một nhóm thấy model trả lời lan man…") rồi hỏi cách xử lý; đáp án vẫn phải có căn cứ trong tài liệu.
- nhieu_buoc: cần nối ≥ 2 đoạn tài liệu khác nhau mới trả lời được; ghi đủ các mã vào "source_chunk_ids".
- doc_bang / doc_hinh: hỏi dựa trên số liệu trong bảng (ghi "stem_table_ids") hoặc nội dung hình (ghi "stem_image_ids").
- Mỗi phương án nhiễu nhắm vào MỘT lỗi hiểu sai có thật: đảo chiều nhân quả, nhầm hai khái niệm, sai số liệu, khái quát quá mức; ghi vào "misconception".
"""

REVIEW_PROMPT = """Bạn kiểm định một câu hỏi trắc nghiệm so với TÀI LIỆU NGUỒN. Không dùng kiến thức ngoài.
CÂU HỎI (JSON): {question}

TÀI LIỆU NGUỒN:
{evidence}

Kiểm tra: (1) đáp án đúng có căn cứ trong nguồn không; (2) có phương án nhiễu nào cũng đúng theo nguồn không;
(3) câu có lộ đáp án không; (4) diễn đạt có mơ hồ không; (5) mức Bloom thực tế.
Trả về DUY NHẤT JSON:
{{"metrics":{{"grounding":0-100,"distractors":0-100,"clarity":0-100,"leakage":0-100}},
 "bloom":"Nhận biết|Thông hiểu|Vận dụng|Vận dụng cao",
 "evidence_chunk_id":"Cxxx",
 "issues":[{{"kind":"answer_ungrounded|distractor_also_correct|answer_leak|ambiguous|wrong_answer|factual_error",
            "severity":"error|warning","message":"giải thích ngắn bằng tiếng Việt",
            "target_field":"stem|explanation|optionA|optionB|optionC|optionD|correctKey",
            "suggested_replacement":"nội dung thay thế hoàn chỉnh cho trường đó"}}]}}
"leakage" = 100 nghĩa là KHÔNG lộ đáp án.
"""


class LLMQuizEngine(QuizEngine):
    """Quiz generation/review through the multi-provider router (config/llm.yaml, tasks quiz / verify)."""
    name = "llm"

    def __init__(self, plan: Optional[str] = None):
        self.plan = plan

    async def _call(self, parts: List[dict], task: str = "quiz") -> str:
        from app.core.llm import LLMError, Part, llm
        converted = [Part.image(base64.b64decode(p["image_data"]), "image/jpeg") if "image_data" in p
                     else Part(text=p.get("text", "")) for p in parts]
        try:
            res = await llm.complete(task, user=converted, max_tokens=16000, temperature=0.3, plan=self.plan)
        except LLMError as e:
            raise RuntimeError(str(e))
        return res.text

    def _image_parts(self, doc: ParsedDocument, image_ids: List[str], limit: int = 8) -> List[dict]:
        from app.edu import storage
        parts = []
        for iid in image_ids[:limit]:
            img = doc.images.get(iid)
            if not img or not img.mime.startswith("image/") or img.mime in ("image/x-wmf", "image/x-emf", "image/svg+xml"):
                continue
            try:
                from PIL import Image
                with Image.open(storage.path("docs", doc.doc_id, img.path)) as im:
                    buf = io.BytesIO()
                    im.convert("RGB").save(buf, "JPEG", quality=85)  # llm_client declares image/jpeg
                parts.append({"text": f"[Hình {iid}]"})
                parts.append({"image_data": base64.b64encode(buf.getvalue()).decode()})
            except Exception as e:
                logger.debug("skip image %s: %s", iid, e)
        return parts

    async def generate(self, doc: ParsedDocument, req: GenerateQuizRequest) -> List[QuizQuestion]:
        retriever = ChunkRetriever(doc.chunks)
        prefix = doc.doc_id.split("_")[-1][:4].upper()
        # batch chunks so long documents still fit and questions spread across the lesson
        batches: List[List[Chunk]] = []
        cur, size = [], 0
        for c in doc.chunks:
            if size + len(c.text) > 12000 and cur:
                batches.append(cur)
                cur, size = [], 0
            cur.append(c)
            size += len(c.text)
        if cur:
            batches.append(cur)
        per_batch = [req.num_questions // len(batches) + (1 if i < req.num_questions % len(batches) else 0)
                     for i in range(len(batches))]

        async def run(batch: List[Chunk], n: int) -> List[dict]:
            if n <= 0:
                return []
            ctx = "\n\n".join(f"[{c.id.split('-')[-1]}] ({' > '.join(c.heading_path)})\n{c.text}" for c in batch)
            prompt = GEN_PROMPT.format(n=n, language=req.language, alloc=_allocate(n, req.bloom_mix),
                                       types=", ".join(req.question_types), context=ctx,
                                       depth=DEPTH_RULES if req.depth else "")
            parts = [{"text": prompt}]
            if req.include_images:
                parts += self._image_parts(doc, [i for c in batch for i in c.image_ids])
            data = _json_from_text(await self._call(parts))
            return data if isinstance(data, list) else data.get("questions", [])

        results = await asyncio.gather(*(run(b, n) for b, n in zip(batches, per_batch)), return_exceptions=True)
        out: List[QuizQuestion] = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("quiz batch failed: %s", r)
                continue
            for raw in r:
                cid = raw.get("source_chunk_id")
                if cid and not str(cid).startswith(prefix):
                    raw["source_chunk_id"] = f"{prefix}-{cid}"
                out.append(normalise_question(raw, len(out) + 1, prefix, doc.doc_id, retriever))
        return out

    async def review(self, q: QuizQuestion, evidence: List[Chunk]) -> Optional[dict]:
        payload = q.model_dump(include={"type", "stem", "options", "correct_key", "answer_text", "explanation"})
        ev = "\n\n".join(f"[{c.id}] {c.text}" for c in evidence) or "(không tìm thấy đoạn liên quan)"
        data = _json_from_text(await self._call([{"text": REVIEW_PROMPT.format(
            question=json.dumps(payload, ensure_ascii=False), evidence=ev)}], task="verify"))
        return data if isinstance(data, dict) else None


GeminiQuizEngine = LLMQuizEngine        # backwards-compatible name (QUIZ_ENGINE=gemini)


# =========================================================================== BE_Zentus adapter
def _load_callable(spec: str) -> Callable:
    """'package.module:function' -> callable, importing from ZENTUS_PATH."""
    if settings.ZENTUS_PATH and os.path.isdir(settings.ZENTUS_PATH) and settings.ZENTUS_PATH not in sys.path:
        sys.path.insert(0, settings.ZENTUS_PATH)
    module_name, _, attr = spec.partition(":")
    obj = importlib.import_module(module_name)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


async def _maybe_await(fn: Callable, **kwargs):
    sig = inspect.signature(fn)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters} \
        if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()) else kwargs
    if inspect.iscoroutinefunction(fn):
        return await fn(**accepted)
    return await asyncio.to_thread(fn, **accepted)


class ZentusQuizEngine(QuizEngine):
    """Calls your BE_Zentus quiz core.

    Configure in .env:
      ZENTUS_PATH=E:/Python_Project/VinAI_Lab/BE_Zentus
      ZENTUS_GENERATE_FN=<module>:<function>     e.g. app.services.quiz.generator:generate_quiz
      ZENTUS_EVALUATE_FN=<module>:<function>     (optional)

    The function is called with whichever of these keyword args it declares:
      text / content / document (markdown of the doc), chunks (list of dicts with id/text),
      num_questions / n, language, bloom_mix, question_types, images (list of {id,url,path})
    It may be sync or async and may return a list of dicts, a dict with "questions",
    pydantic models, or a JSON string — normalise_question() maps common key names.
    """
    name = "zentus"

    def __init__(self):
        if not settings.ZENTUS_GENERATE_FN:
            raise RuntimeError("ZENTUS_GENERATE_FN is not set")
        self.generate_fn = _load_callable(settings.ZENTUS_GENERATE_FN)
        self.evaluate_fn = _load_callable(settings.ZENTUS_EVALUATE_FN) if settings.ZENTUS_EVALUATE_FN else None

    async def generate(self, doc: ParsedDocument, req: GenerateQuizRequest) -> List[QuizQuestion]:
        from app.edu import storage
        chunks = [c.model_dump() for c in doc.chunks]
        images = [{"id": i.id, "url": i.url, "path": storage.path("docs", doc.doc_id, i.path), "alt": i.alt}
                  for i in doc.images.values()]
        result = await _maybe_await(
            self.generate_fn, text=doc.markdown, content=doc.markdown, document=doc.markdown, chunks=chunks,
            num_questions=req.num_questions, n=req.num_questions, language=req.language,
            bloom_mix=req.bloom_mix, question_types=req.question_types, images=images)
        if isinstance(result, str):
            result = _json_from_text(result)
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        if isinstance(result, dict):
            result = result.get("questions") or result.get("data") or result.get("items") or []
        retriever = ChunkRetriever(doc.chunks)
        prefix = doc.doc_id.split("_")[-1][:4].upper()
        out = []
        for raw in result:
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump()
            elif not isinstance(raw, dict):
                raw = vars(raw)
            out.append(normalise_question(raw, len(out) + 1, prefix, doc.doc_id, retriever))
        return out

    async def review(self, q: QuizQuestion, evidence: List[Chunk]) -> Optional[dict]:
        if not self.evaluate_fn:
            return None
        res = await _maybe_await(self.evaluate_fn, question=q.model_dump(), evidence=[c.model_dump() for c in evidence],
                                 chunks=[c.model_dump() for c in evidence])
        return res.model_dump() if hasattr(res, "model_dump") else res


# =========================================================================== factory
_cache: Dict[str, QuizEngine] = {}


def get_engine(name: Optional[str] = None, plan: Optional[str] = None) -> QuizEngine:
    """llm (default, provider router) | zentus (external BE_Zentus fn, falls back to llm)."""
    name = (name or settings.QUIZ_ENGINE or "llm").lower()
    if name == "zentus":
        if "zentus" not in _cache:
            try:
                _cache["zentus"] = ZentusQuizEngine()
            except Exception as e:
                logger.warning("BE_Zentus engine unavailable (%s) — falling back to the LLM router", e)
        if "zentus" in _cache:
            return _cache["zentus"]
    return LLMQuizEngine(plan=plan)
