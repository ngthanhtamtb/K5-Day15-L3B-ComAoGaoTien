"""Slide framework ("khung slide") for narrated lesson decks.

Why these rules (summary of the analysis, see EDUGUARD.md "Khung slide"):

* Lesson arc (Gagné, rút gọn): mở bài -> nội dung chính -> nội dung -> tóm tắt -> câu hỏi nhanh -> kết.
  Retrieval practice (một câu hỏi cuối bài) giúp nhớ lâu hơn đọc lại.
* Assertion–Evidence (Alley): tiêu đề slide là MỘT câu khẳng định ngắn, thân slide là bằng chứng
  trực quan (hình / bảng / sơ đồ / so sánh) thay vì đoạn chữ dài.
* Mayer multimedia: một ý mỗi slide (segmenting), bớt chữ (coherence), lời đọc không lặp nguyên văn
  chữ trên slide (redundancy), chú thích nằm cạnh hình (spatial contiguity), hình + giọng (modality).

What is enforced here, deterministically (no model call):
* every layout's required data must exist, otherwise the slide falls back to `bullets`
  (a table/figure must be a real id from the document; a page scan is never shown as a figure)
* a "big number" (key_fact) must literally occur in the source chunk it cites — numbers are never invented
* limits: ≤ 4 points, ≤ 14 words per point, title ≤ 90 characters, 3–6 process steps, 2 comparison columns
* framing slides (agenda, closing) carry only "dẫn dắt" sentences built from the slide titles — no new facts,
  so they are not sent to the checker; everything with content (incl. summary and the quiz answer) is checked.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# layout id -> (vietnamese name, what it is for, json fields the model fills)
LAYOUTS: Dict[str, Tuple[str, str, str]] = {
    "bullets":    ("Ý chính", "một ý, 2–4 gạch đầu dòng ngắn", '"y_chinh":["..."]'),
    "image_text": ("Hình + ý", "một hình của tài liệu là bằng chứng cho tiêu đề", '"image_ids":["<id hình>"],"y_chinh":["..."]'),
    "table":      ("Bảng", "một bảng của tài liệu + một câu rút ra", '"table_ids":["<id bảng>"],"y_chinh":["<điều rút ra>"]'),
    "comparison": ("So sánh", "hai khái niệm / phương án đặt cạnh nhau",
                   '"cot":[{"ten":"A","y":["..."]},{"ten":"B","y":["..."]}]'),
    "process":    ("Quy trình", "3–6 bước theo thứ tự", '"buoc":[{"ten":"Bước","mo_ta":"..."}]'),
    "key_fact":   ("Khái niệm / con số", "một định nghĩa hoặc một con số then chốt có trong tài liệu",
                   '"nhan_manh":{"gia_tri":"<thuật ngữ hoặc con số có trong đoạn nguồn>","giai_thich":"..."}'),
}
CONTENT_LAYOUTS = tuple(LAYOUTS)
FRAME_LAYOUTS = ("cover", "agenda", "summary", "check", "end")
ALL_LAYOUTS = CONTENT_LAYOUTS + FRAME_LAYOUTS

KHUNG = {
    # teacher-facing choice: full lesson arc or content only
    "bai_giang": ("cover", "agenda", "*", "summary", "check", "end"),
    "gon": ("cover", "*", "end"),
}

MAX_POINTS, MAX_WORDS, MAX_TITLE = 4, 14, 90


def catalog_prompt() -> str:
    return "\n".join(f"- {k}: {v[1]}. Trường: {v[2]}" for k, v in LAYOUTS.items())


def _words(text: str, limit: int = MAX_WORDS) -> str:
    w = str(text or "").split()
    return " ".join(w[:limit]) + ("…" if len(w) > limit else "")


def is_figure(img: Any) -> bool:
    """A document image worth putting on a slide: not a page scan, a real raster/vector image, and not a
    logo / icon (drawn smaller than ~100×100 pt on the page, or < 160 px when there is no bbox)."""
    if img is None or (getattr(img, "kind", None) or "figure") == "page_scan":
        return False
    mime = str(getattr(img, "mime", "image/") or "image/")
    if not mime.startswith("image/") or mime in ("image/x-wmf", "image/x-emf"):
        return False
    bbox = getattr(img, "bbox", None) or []
    if len(bbox) == 4:
        w, h = abs(bbox[2] - bbox[0]), abs(bbox[3] - bbox[1])
        return w * h >= 100 * 100 and max(w, h) >= 120
    px = [v for v in (getattr(img, "width_px", None), getattr(img, "height_px", None)) if v]
    return not px or max(px) >= 160


_STEP_LABEL = re.compile(r"^\s*(bước|step|giai đoạn)\s*\d+\s*[:.\-–]?\s*$", re.I)


def _clean_points(items: Any, limit: int = MAX_POINTS) -> List[str]:
    if isinstance(items, str):              # models sometimes send one string instead of a list
        items = [x for x in re.split(r"\n+|;\s+", items) if x.strip()]
    out = []
    for x in items or []:
        t = _words(x if isinstance(x, str) else (x or {}).get("text", ""))
        if t and t not in out:
            out.append(t)
    return out[:limit]


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def fact_in_source(value: str, sources: List[str]) -> bool:
    """A highlighted value is allowed only if it appears in a cited chunk (numbers: every number in
    it must appear; terms: case-insensitive substring)."""
    value = (value or "").strip()
    if not value or not sources:
        return False
    blob = " ".join(sources)
    nums = _NUM.findall(value)
    if nums:
        return all(n in blob for n in nums)
    return value.lower() in blob.lower()


def normalize(raw: Dict[str, Any], *, images: Dict[str, Any], tables: Dict[str, Any],
              chunk_text: Dict[str, str]) -> Dict[str, Any]:
    """One model-proposed content slide -> a slide that satisfies its layout, or a bullets fallback."""
    layout = raw.get("layout") if raw.get("layout") in CONTENT_LAYOUTS else None
    title = re.sub(r"\s+", " ", str(raw.get("tieu_de") or "")).strip()[:MAX_TITLE] or "Slide"
    points = _clean_points(raw.get("y_chinh"))
    doan = [d for d in (raw.get("doan") or []) if (d.get("text") if isinstance(d, dict) else d)]
    texts = [str(d.get("text") if isinstance(d, dict) else d).strip() for d in doan]
    cited = [str(d.get("segment_id") or "") if isinstance(d, dict) else "" for d in doan]   # aligned with texts
    cited_text = [chunk_text[c] for c in cited if c in chunk_text]

    imgs = [i for i in (raw.get("image_ids") or []) if i in images and is_figure(images[i])][:1]
    tbls = [t for t in (raw.get("table_ids") or []) if t in tables][:1]
    extra: Dict[str, Any] = {}

    if layout is None:                       # infer from what the slide carries
        layout = "table" if tbls else "image_text" if imgs else "bullets"
    if layout == "table" and not tbls:
        layout = "image_text" if imgs else "bullets"
    if layout == "image_text" and not imgs:
        layout = "table" if tbls else "bullets"
    if layout == "comparison":
        cols = [{"ten": _words(c.get("ten"), 6), "y": _clean_points(c.get("y"), 3)}
                for c in (raw.get("cot") or []) if isinstance(c, dict)]
        cols = [c for c in cols if c["ten"] and c["y"]]
        if len(cols) >= 2:
            extra["cot"] = cols[:2]
        else:
            points = points or [p for c in cols for p in c["y"]][:MAX_POINTS]
            layout = "bullets"
    elif layout == "process":
        steps = []
        for b in raw.get("buoc") or []:
            if not isinstance(b, dict) or not (b.get("ten") or b.get("mo_ta")):
                continue
            name, desc = _words(b.get("ten"), 8), _words(b.get("mo_ta"), 22)
            if not name or _STEP_LABEL.match(name):      # "Bước 2" says nothing: the description becomes the name
                name, desc = _words(desc, 8), ""
            steps.append({"ten": name, "mo_ta": desc})
        if 3 <= len(steps):
            extra["buoc"] = steps[:6]
        else:
            points = points or [s["ten"] or s["mo_ta"] for s in steps]
            layout = "bullets"
    elif layout == "key_fact":
        f = raw.get("nhan_manh") or {}
        value = _words(f.get("gia_tri"), 8) if isinstance(f, dict) else ""
        if value and fact_in_source(value, cited_text):
            extra["nhan_manh"] = {"gia_tri": value, "giai_thich": _words(f.get("giai_thich"), 24)}
        else:                                # not literally in the cited source: never show it big
            layout = "bullets"

    if layout == "bullets" and (imgs or tbls):    # a valid figure/table survived the fallback: use it
        layout = "image_text" if imgs else "table"
    if layout in ("bullets", "image_text") and not points:
        points = [_words(t, 10) for t in texts[:3]]
    return {"tieu_de": title, "phan": _words(raw.get("phan"), 6), "layout": layout, "y_chinh": points,
            "image_ids": imgs if layout == "image_text" else [], "table_ids": tbls if layout == "table" else [],
            "extra": extra, "doan": texts, "cited": cited}


def outline(khung: str, content: List[Dict[str, Any]], deck: Dict[str, Any], title: str) -> List[Dict[str, Any]]:
    """Wrap normalized content slides in the lesson arc. Framing narration is built from titles only."""
    plan = KHUNG.get(khung) or KHUNG["bai_giang"]
    out: List[Dict[str, Any]] = []
    titles = [s["tieu_de"] for s in content]
    for part in plan:
        if part == "*":
            out.extend(content)
        elif part == "agenda" and len(content) >= 2:
            out.append({"layout": "agenda", "tieu_de": "Nội dung chính", "phan": "", "y_chinh": titles[:6],
                        "image_ids": [], "table_ids": [], "extra": {},
                        "doan": [], "dan_dat": [f"Bài hôm nay gồm {len(content)} phần: " + "; ".join(titles[:6]) + "."]})
        elif part == "summary":
            pts = deck.get("tom_tat") or []
            pts = [p for p in pts if isinstance(p, dict) and str(p.get("text") or "").strip()][:4]
            if pts:
                out.append({"layout": "summary", "tieu_de": "Tóm tắt", "phan": "",
                            "y_chinh": [_words(p["text"], 14) for p in pts], "image_ids": [], "table_ids": [],
                            "extra": {}, "doan": [str(p["text"]).strip() for p in pts],
                            "cited": [str(p.get("segment_id") or "") for p in pts]})
        elif part == "check":
            q = deck.get("cau_hoi_nhanh") or {}
            if isinstance(q, dict) and str(q.get("cau_hoi") or "").strip() and str(q.get("dap_an") or "").strip():
                out.append({"layout": "check", "tieu_de": "Câu hỏi nhanh", "phan": "", "y_chinh": [],
                            "image_ids": [], "table_ids": [],
                            "extra": {"cau_hoi": _words(q["cau_hoi"], 30), "dap_an": _words(q["dap_an"], 30)},
                            # the question is spoken as a lead-in; the answer is a claim and gets checked
                            "dan_dat": [str(q["cau_hoi"]).strip()],
                            "doan": [f"Đáp án: {str(q['dap_an']).strip()}"],
                            "cited": [str(q.get("segment_id") or "")]})
    return out
