"""Document -> narrated HTML slide deck in one job (no script step for the teacher):

  1. design slides + narration from chunks spread over the whole document (task "script"), following the
     slide framework in app/edu/slide_frame.py (lesson arc + one frame per slide, normalised deterministically)
  2. check every narration sentence against the source (KHOP / SAI / THIEU / TU_CHOI)
  3. attach figures / tables from the chunks each slide actually cites
  4. narrate (TTS) — if the voice provider fails, the deck is still produced, without audio
  5. render a standalone HTML deck (app/edu/html_deck.py)
The teacher then fixes only what is flagged; re-voicing re-bills only edited sentences.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.llm import collect
from app.edu import docparse, html_deck
from app.edu.scripts import service as scripts
from app.edu.scripts.models import CreateScriptRequest

logger = logging.getLogger(__name__)


async def build_deck(doc_id: str, *, so_slide: int = 6, chu_de: Optional[str] = None, title: Optional[str] = None,
                     voice: Optional[str] = None, speed: float = 1.0, narrate: bool = True, khung: str = "bai_giang",
                     job=None, plan: Optional[str] = None, plan_ctx=None) -> Dict[str, Any]:
    def step(pct: int, msg: str):
        if job is not None:
            job.progress(pct, msg)

    doc = docparse.load(doc_id)
    if doc is None:
        raise scripts.NotFound("document not found")
    with collect() as trace:
        step(5, "Đang thiết kế slide theo khung bài giảng")
        sc = await scripts.create(CreateScriptRequest(doc_id=doc_id, chu_de=chu_de or None, title=title,
                                                      so_slide=so_slide, doan_moi_slide=3,
                                                      khung=khung), plan=plan)
        step(45, "Đã kiểm từng câu với tài liệu")
    sc.trace = trace.summary()
    scripts.save(sc)

    voice_result, voice_error = None, None
    if narrate:
        step(50, "Đang sinh giọng đọc")
        try:
            from app.edu.voice.script_voice import voice_script

            class _Sub:  # map voice progress (0-90) into 50-90 of this job
                def progress(self, pct, msg=""):
                    step(50 + int(pct * 0.45), msg)

            voice_result = await voice_script(sc.id, voice, speed, job=_Sub(), plan_ctx=plan_ctx)
        except Exception as e:  # no API key, provider down… the deck is still useful
            logger.warning("deck %s: narration failed: %s", sc.id, e)
            voice_error = f"Chưa sinh được giọng đọc: {e}"[:300]
        sc = scripts.get(sc.id)

    step(95, "Đang dựng slide HTML")
    url = html_deck.save(sc, doc)
    counts = scripts.counts(sc)
    return {"scriptId": sc.id, "title": sc.title, "htmlUrl": url, "slides": len(sc.slides),
            "needsReview": counts.get("canXem", 0), "labels": counts.get("nhan", {}),
            "voice": voice_result, "voiceError": voice_error, "trace": sc.trace}


def render_html(script_id: str) -> str:
    sc = scripts.get(script_id)
    return html_deck.save(sc, docparse.load(sc.doc_id))
