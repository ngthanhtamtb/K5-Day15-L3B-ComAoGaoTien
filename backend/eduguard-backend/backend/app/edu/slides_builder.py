"""Approved script -> PPTist slides, using RAGslides' template engine (SlideProcessor).

Differences from RAGslides' own generator:
  * input is the gate-1 approved script, not the whole document stuffed into a prompt
  * template image placeholders are filled with figures FROM THE SOURCE DOCUMENT (cited), not
    with AI-generated pictures
  * each slide carries `remark` (narration) and an `eduguard` block: segment labels, source
    chunk ids and the audio track markers, so the viewer/editor can show labels next to text
  * when the slide was voiced, a PPTist audio element (autoplay) is attached
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.core.pptagent.slide_processor import SlideProcessor
from app.edu import docparse
from app.edu.scripts.models import Script
from app.edu.voice.service import audio_element, text_to_remark_html

TEMPLATE_DIR = "data/templates"


def list_templates() -> List[Dict[str, Any]]:
    import json
    out = []
    for name in sorted(os.listdir(TEMPLATE_DIR)):
        if name.startswith("template_") and name.endswith(".json"):
            with open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8") as fh:
                d = json.load(fh)
            out.append({"id": name[:-5], "title": d.get("title"), "width": d.get("width"), "height": d.get("height"),
                        "coverUrl": d.get("cover_url")})
    return out


def _load_template(template: str):
    import json
    name = os.path.basename(template)
    path = os.path.join(TEMPLATE_DIR, name if name.endswith(".json") else f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"template {template} not found")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["slides"], float(data.get("width", 1000)), float(data.get("height", 562.5))


def _short(text: str, words: int = 7) -> str:
    w = text.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def _items(slide) -> List[Dict[str, str]]:
    segs = [s.text for s in slide.doan]
    if slide.y_chinh:
        return [{"title": y, "text": (segs[i] if i < len(segs) else "")[:220]} for i, y in enumerate(slide.y_chinh[:4])]
    return [{"title": _short(t), "text": t[:220]} for t in segs[:4]] or [{"title": slide.tieu_de, "text": ""}]


async def build_slides(sc: Script, template: str = "template_1", only_approved: bool = True) -> Dict[str, Any]:
    from app.edu.scripts.service import approved_slides
    template_slides, width, height = _load_template(template)
    doc = docparse.load(sc.doc_id)
    proc = SlideProcessor()
    src_slides = approved_slides(sc) if only_approved else sc.slides

    out: List[Dict[str, Any]] = []

    async def emit(ai: Dict[str, Any], meta: Dict[str, Any], remark: str = "", audio: Optional[dict] = None,
                   image_ids: Optional[List[str]] = None):
        if doc and image_ids:
            proc.img_pool = [{"id": i, "src": doc.images[i].url, "width": doc.images[i].width_px or 1200,
                              "height": doc.images[i].height_px or 800} for i in image_ids if i in doc.images]
        else:
            proc.img_pool = []
        mapped = await proc._map_ai_slide_to_template(ai, template_slides)
        if not mapped:
            return
        mapped = dict(mapped)
        elements = list(mapped.get("elements", []))
        used = {e.get("src") for e in elements if e.get("type") == "image"}
        # figures that found no placeholder in the template: place them on the right, keep the source link
        for i in (image_ids or []):
            img = doc.images.get(i) if doc else None
            if img and img.url not in used:
                w = width * 0.32
                h = w * (img.height_px or 3) / (img.width_px or 4)
                elements.append({"type": "image", "id": f"src-{i}", "src": img.url, "left": width - w - 24,
                                 "top": (height - h) / 2, "width": w, "height": h, "fixedRatio": True, "rotate": 0})
        if audio and audio.get("url"):
            elements.append(audio_element(mapped.get("id", "s"), audio["url"], audio.get("ext", "mp3"), width, height))
        mapped["elements"] = elements
        if remark:
            mapped["remark"] = text_to_remark_html(remark)
        mapped["eduguard"] = meta
        out.append(mapped)

    await emit({"type": "cover", "data": {"title": sc.title, "text": doc.filename if doc else ""}},
               {"kind": "cover", "scriptId": sc.id})
    for s in src_slides:
        await emit({"type": "content", "data": {"title": s.tieu_de, "items": _items(s)}},
                   {"kind": "content", "scriptId": sc.id, "scriptSlide": s.index, "layout": s.layout,
                    "segments": [{"id": g.id, "nhan": g.nhan, "segmentId": g.segment_id, "quyetDinh": g.quyet_dinh,
                                  "voice": g.voice} for g in s.doan],
                    "tableIds": s.table_ids, "audio": s.audio},
                   remark=" ".join(g.text for g in s.doan), audio=s.audio, image_ids=s.image_ids)
    await emit({"type": "end", "data": {"title": "Cảm ơn", "text": sc.title}}, {"kind": "end", "scriptId": sc.id})
    return {"scriptId": sc.id, "template": template, "width": width, "height": height, "slides": out,
            "status": "cho_duyet"}
