"""Slides + voice.

Works directly on PPTist slide JSON (the format RAGslides already generates and stores in
PresentationPage.page_data):
  * speaker script  = slide["remark"] (PPTist's notes field, HTML)  <->  PresentationPage.speaker_notes
  * narration audio = a PPTist audio element {type:"audio", autoplay:true, src:...} on the slide,
    so PPTist plays it in presentation mode and it stays editable/removable in the editor.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.core.config import settings
from app.edu import storage
from app.edu.tts import TTSResult, concat_audio, get_provider, split_sentences, wav_duration

logger = logging.getLogger(__name__)
VOICE_EL_PREFIX = "voice-"


# --------------------------------------------------------------------------- text helpers
def html_to_text(value: Optional[str]) -> str:
    if not value:
        return ""
    if "<" not in value:
        return value.strip()
    return re.sub(r"\n{2,}", "\n", BeautifulSoup(value, "html.parser").get_text("\n")).strip()


def text_to_remark_html(text: str) -> str:
    return "".join(f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip())


def slide_text(slide: Dict[str, Any]) -> str:
    """Visible text of a PPTist slide, top-to-bottom, left-to-right."""
    items = []
    for el in slide.get("elements", []):
        t = el.get("type")
        txt = ""
        if t == "text":
            txt = html_to_text(el.get("content"))
        elif t == "shape" and el.get("text"):
            txt = html_to_text(el["text"].get("content"))
        elif t == "table":
            rows = el.get("data") or []
            txt = "\n".join(" | ".join(html_to_text(c.get("text", "")) for c in row) for row in rows)
        elif t == "latex":
            txt = el.get("latex", "")
        if txt:
            items.append((el.get("top", 0), el.get("left", 0), txt))
    items.sort()
    return "\n".join(t for _, _, t in items)


# --------------------------------------------------------------------------- TTS with cache
def cache_key(text: str, voice: Optional[str], speed: float) -> str:
    provider = get_provider()
    voice = voice or settings.TTS_DEFAULT_VOICE
    return hashlib.sha256(f"{provider.name}|{voice}|{speed}|{text.strip()}".encode()).hexdigest()[:32]


def cached_clip(key: str) -> Optional[Dict[str, Any]]:
    for ext in ("mp3", "wav", "ogg", "m4a"):
        p = os.path.join(storage.edu_root(), "audio", f"{key}.{ext}")
        if os.path.exists(p):
            meta = storage.load_json("audio", f"{key}.json") or {}
            return {"url": storage.url_for("audio", f"{key}.{ext}"), "path": p, "duration": meta.get("duration"),
                    "ext": ext, "timings": meta.get("timings"), "cached": True}
    return None


async def synthesize(text: str, voice: Optional[str] = None, speed: float = 1.0) -> Dict[str, Any]:
    """Synthesize narration; identical text/voice/speed is served from cache (no re-billing).
    Long text is split at sentence boundaries under TTS_MAX_CHARS; every request goes through the
    shared rate limiter (TTS_RPM, TTS_CONCURRENCY) with retries on 429/5xx (TTS_MAX_RETRIES)."""
    from .limits import actual_units, with_retries
    provider = get_provider()
    voice = voice or settings.TTS_DEFAULT_VOICE
    text = text.strip()
    if not text:
        raise ValueError("empty script")
    key = cache_key(text, voice, speed)
    hit = cached_clip(key)
    if hit:
        return {**hit, "provider": provider.name, "voice": voice, "billedChars": 0, "requests": 0}
    parts = split_sentences(text, settings.TTS_MAX_CHARS)
    results: List[TTSResult] = []
    for part in parts:  # pieces of ONE clip stay in order; parallelism happens across clips
        results.append(await with_retries(lambda p=part: provider.synthesize(p, voice, speed)))
    res = concat_audio(results)
    duration = res.duration_sec or (wav_duration(res.audio) if res.ext == "wav" else None) or _mp3_duration(res.audio)
    timings = res.timings if len(results) == 1 else None
    path = storage.path("audio", f"{key}.{res.ext}")
    with open(path, "wb") as fh:
        fh.write(res.audio)
    storage.save_json({"duration": duration, "voice": voice, "speed": speed, "chars": len(text),
                       "timings": timings}, "audio", f"{key}.json")
    return {"url": storage.url_for("audio", f"{key}.{res.ext}"), "path": path, "duration": duration, "ext": res.ext,
            "timings": timings, "cached": False, "provider": provider.name, "voice": voice,
            "billedChars": len(text), "requests": len(parts),
            "units": actual_units(len(text), duration or 0, len(parts))}


def _mp3_duration(data: bytes) -> Optional[float]:
    try:
        import io
        from mutagen.mp3 import MP3
        return MP3(io.BytesIO(data)).info.length
    except Exception:
        return None


# --------------------------------------------------------------------------- scripts
SCRIPT_PROMPT = """Bạn là giáo viên đang thuyết trình. Viết lời giảng (speaker script) cho slide dưới đây.
- Ngôn ngữ: {language}. Giọng: {style}. Độ dài: {words} từ.
- Nói tự nhiên như đang giảng, không đọc lại nguyên văn các gạch đầu dòng, không dùng markdown.
- Chỉ nói những gì có trong slide{grounding}.
Tiêu đề bài: {lesson}
Slide {index}/{total}:
{content}
{context}
Chỉ trả về lời giảng."""


async def write_script(slide: Dict[str, Any], index: int, total: int, lesson: str, language: str,
                       style: str, words: int, context: str = "") -> str:
    from app.core.llm import LLMError, llm   # multi-provider router, task "script"
    prompt = SCRIPT_PROMPT.format(
        language=language, style=style, words=words, lesson=lesson, index=index + 1, total=total,
        content=slide_text(slide) or "(slide chỉ có hình ảnh)",
        grounding=" và tài liệu tham chiếu" if context else "",
        context=f"\nTài liệu tham chiếu:\n{context}" if context else "")
    try:
        res = await llm.complete("script", user=prompt, max_tokens=2048, temperature=0.5)
    except LLMError as e:
        raise RuntimeError(str(e))
    return res.text.strip()


async def ensure_scripts(slides: List[Dict[str, Any]], lesson: str = "", language: str = "Vietnamese",
                         style: str = "thân thiện, rõ ràng", words: int = 90, overwrite: bool = False,
                         doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
    retriever = None
    if doc_id:
        from app.edu.docparse import load
        from app.edu.retrieval import ChunkRetriever
        doc = load(doc_id)
        retriever = ChunkRetriever(doc.chunks) if doc else None
    sem = asyncio.Semaphore(4)

    async def one(i: int, s: Dict[str, Any]) -> Dict[str, Any]:
        if html_to_text(s.get("remark")) and not overwrite:
            return s
        ctx = ""
        if retriever:
            ctx = "\n".join(c.text[:600] for c, _ in retriever.search(slide_text(s), k=2))
        async with sem:
            script = await write_script(s, i, len(slides), lesson, language, style, words, ctx)
        return {**s, "remark": text_to_remark_html(script)}

    return list(await asyncio.gather(*(one(i, s) for i, s in enumerate(slides))))


# --------------------------------------------------------------------------- attach audio
def audio_element(slide_id: str, url: str, ext: str, width: float, height: float) -> Dict[str, Any]:
    size = 48
    return {"type": "audio", "id": f"{VOICE_EL_PREFIX}{slide_id}"[:40], "left": width - size - 16,
            "top": height - size - 16, "width": size, "height": size, "rotate": 0, "fixedRatio": True,
            "color": "#2563EB", "loop": False, "autoplay": True, "src": url, "ext": ext}


async def voice_slides(slides: List[Dict[str, Any]], voice: Optional[str] = None, speed: float = 1.0,
                       embed: bool = True, width: float = 1000, height: float = 562.5) -> Dict[str, Any]:
    """TTS every slide's remark; returns updated slides + a manifest for a custom player."""
    out_slides, manifest = [], []
    for i, s in enumerate(slides):
        script = html_to_text(s.get("remark"))
        entry = {"index": i, "slideId": s.get("id"), "script": script, "audioUrl": None, "duration": None}
        elements = [e for e in s.get("elements", []) if not str(e.get("id", "")).startswith(VOICE_EL_PREFIX)]
        if script:
            audio = await synthesize(script, voice, speed)
            entry.update(audioUrl=audio["url"], duration=audio["duration"], cached=audio["cached"])
            if embed:
                elements.append(audio_element(s.get("id", f"s{i}"), audio["url"], audio["ext"], width, height))
        out_slides.append({**s, "elements": elements})
        manifest.append(entry)
    return {"slides": out_slides, "manifest": manifest,
            "totalDuration": round(sum(m["duration"] or 0 for m in manifest), 2)}


# --------------------------------------------------------------------------- DB presentations (RAGslides models)
async def voice_presentation(db, presentation_id: str, user_id: int, voice: Optional[str], speed: float,
                             write_missing_scripts: bool, language: str) -> Dict[str, Any]:
    from app.models.presentation import Presentation, PresentationPage
    pres = db.query(Presentation).filter(Presentation.id == presentation_id).first()
    if not pres:
        raise LookupError("presentation not found")
    if pres.owner_id != user_id:
        raise PermissionError("not the owner")
    pages = (db.query(PresentationPage).filter(PresentationPage.presentation_id == presentation_id)
             .order_by(PresentationPage.page_order).all())
    slides = []
    for p in pages:
        data = dict(p.page_data or {})
        data.setdefault("id", str(p.id))
        if p.speaker_notes and not data.get("remark"):
            data["remark"] = text_to_remark_html(p.speaker_notes)
        slides.append(data)
    if write_missing_scripts:
        slides = await ensure_scripts(slides, lesson=pres.title, language=language)
    result = await voice_slides(slides, voice, speed, True, pres.width or 1000, pres.height or 562.5)
    for p, s, m in zip(pages, result["slides"], result["manifest"]):
        p.page_data = s
        p.speaker_notes = m["script"]
        ext = dict(p.ext_info or {})
        ext["voice"] = {"audioUrl": m["audioUrl"], "duration": m["duration"], "voice": voice}
        p.ext_info = ext
    db.commit()
    return result
