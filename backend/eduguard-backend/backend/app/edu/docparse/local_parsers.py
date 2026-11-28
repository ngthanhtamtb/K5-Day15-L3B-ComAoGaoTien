"""Local PDF / PPTX parsing — nothing leaves the server (EDU_PDF_ENGINE=local, the default).

PDF  (PyMuPDF, pdfplumber as table fallback)
  * text blocks in reading order with bbox; headings from font size / bold / "Chương|Bài|Mục…"
  * tables via page.find_tables() -> cells + markdown; text inside a table is not duplicated
  * embedded images with their position (kept even when no "Câu N" is nearby, unlike BE_Zentus)
  * repeated headers/footers and page numbers dropped
  * scanned pages (< 40 chars): OCR through the "vision" LLM route when EDU_OCR_ENABLED, otherwise
    the rendered page is kept as an image block so nothing is silently lost
PPTX (python-pptx)
  * per slide: title -> heading, text frames -> paragraphs/list items (indent level), tables,
    pictures (also inside groups), speaker notes (source="notes") — position kept as bbox
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
import statistics
from collections import Counter
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from .models import ParsedDocument
from .other_parsers import _Builder

logger = logging.getLogger(__name__)

PDF_MIN_TEXT_CHARS = 40
_HEADING_WORD = re.compile(r"^(chương|phần|bài|mục|chapter|section|part|unit|lesson)\b", re.I)
_BULLET = re.compile(r"^\s*([•●▪◦‣\-–—*]|\d+[.)]|[a-zA-Z][.)])\s+")
_DIGITS = re.compile(r"\d+")


def _clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", (s or "").replace(" ", " ")).strip()


def _inside(inner: Tuple[float, float, float, float], outer: Tuple[float, float, float, float]) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] - 1 <= cx <= outer[2] + 1 and outer[1] - 1 <= cy <= outer[3] + 1


# =========================================================================== PDF
def _page_tables(page, pdf_bytes: bytes, page_index: int) -> List[Tuple[Tuple, List[List[str]]]]:
    out = []
    try:
        found = page.find_tables()
        for t in found.tables:
            rows = [[_clean(c or "").replace("\n", " ") for c in r] for r in t.extract()]
            rows = [r for r in rows if any(r)]
            if len(rows) >= 2 and max(len(r) for r in rows) >= 2:
                out.append((tuple(t.bbox), rows))
        return out
    except AttributeError:      # very old PyMuPDF: fall back to pdfplumber
        pass
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            p = pdf.pages[page_index]
            for t in p.find_tables():
                rows = [[_clean(c or "") for c in r] for r in t.extract()]
                if len(rows) >= 2:
                    out.append((tuple(t.bbox), rows))
    except Exception as e:  # tables are a bonus; never fail the whole parse
        logger.debug("pdfplumber tables failed on page %s: %s", page_index + 1, e)
    return out


def _font_stats(doc) -> float:
    sizes: List[float] = []
    for page in doc:
        for b in page.get_text("dict").get("blocks", []):
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    if sp.get("text", "").strip():
                        sizes.extend([round(sp["size"], 1)] * len(sp["text"]))
    return statistics.median(sizes) if sizes else 11.0


def _margin_lines(doc) -> set:
    """Text that repeats in the top/bottom 7% band on many pages = header/footer."""
    counts: Counter = Counter()
    n = len(doc)
    for page in doc:
        h = page.rect.height
        seen = set()
        for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
            if y1 < h * 0.07 or y0 > h * 0.93:
                key = _DIGITS.sub("#", _clean(text).lower())
                if key and key not in seen:
                    seen.add(key)
                    counts[key] += 1
    return {k for k, c in counts.items() if n >= 3 and c >= max(2, n // 2)} | {"#"}


async def parse_pdf_local(file_bytes: bytes, filename: str, doc_id: str, data_dir: str,
                          url_prefix: str) -> ParsedDocument:
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    bld = _Builder(data_dir, url_prefix)
    body_size = _font_stats(doc)
    margins = _margin_lines(doc)
    seen_images: set = set()
    stats = {"pages": len(doc), "ocr_pages": [], "scan_pages_without_ocr": [], "tables": 0, "images": 0}

    for pi, page in enumerate(doc):
        pno = pi + 1
        h = page.rect.height
        items: List[Tuple[float, float, str, dict]] = []   # (y0, x0, kind, payload)

        tables = _page_tables(page, file_bytes, pi)
        for bbox, rows in tables:
            items.append((bbox[1], bbox[0], "table", {"rows": rows, "bbox": bbox}))

        # ---------------------------------------------------------------- images
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                info = doc.extract_image(xref)
                rects = page.get_image_rects(xref)
            except Exception:
                continue
            data = info.get("image") or b""
            w, hh = int(info.get("width") or 0), int(info.get("height") or 0)
            if not data or min(w, hh) < settings.EDU_MIN_IMAGE_PX or not rects:
                continue
            digest = hashlib.sha1(data).hexdigest()
            if digest in seen_images:
                continue
            seen_images.add(digest)
            r = rects[0]
            items.append((r.y0, r.x0, "image", {"data": data, "ext": info.get("ext") or "png", "size": (w, hh),
                                                 "bbox": (r.x0, r.y0, r.x1, r.y1)}))

        # ---------------------------------------------------------------- text
        page_chars = 0
        for b in page.get_text("dict", sort=True).get("blocks", []):
            if b.get("type") != 0:
                continue
            bbox = tuple(b["bbox"])
            if any(_inside(bbox, t[0]) for t in tables):
                continue
            lines, sizes, bold_chars, all_chars = [], [], 0, 0
            for line in b.get("lines", []):
                txt = "".join(sp.get("text", "") for sp in line.get("spans", []))
                if txt.strip():
                    lines.append(_clean(txt))
                for sp in line.get("spans", []):
                    t = sp.get("text", "").strip()
                    if t:
                        sizes.append(sp.get("size", body_size))
                        all_chars += len(t)
                        if sp.get("flags", 0) & 16 or "bold" in sp.get("font", "").lower():
                            bold_chars += len(t)
            text = _clean(" ".join(lines))
            if not text:
                continue
            page_chars += len(text.replace(" ", ""))
            if (bbox[3] < h * 0.07 or bbox[1] > h * 0.93) and _DIGITS.sub("#", text.lower()) in margins:
                continue
            size = max(sizes) if sizes else body_size
            words = len(text.split())
            level = None
            if words <= 16:
                if size >= body_size * 1.5:
                    level = 1
                elif size >= body_size * 1.2:
                    level = 2
                elif _HEADING_WORD.match(text) or (all_chars and bold_chars / all_chars > 0.9 and words <= 12):
                    level = 3
            items.append((bbox[1], bbox[0], "text", {"text": text, "level": level, "bbox": bbox, "lines": lines}))

        # ---------------------------------------------------------------- scanned page
        if page_chars < PDF_MIN_TEXT_CHARS:
            png = page.get_pixmap(dpi=150, alpha=False).tobytes("png")
            ocr_text = ""
            if settings.EDU_OCR_ENABLED:
                ocr_text = await _ocr_png(png)
            if ocr_text:
                stats["ocr_pages"].append(pno)
                for para in re.split(r"\n\s*\n", ocr_text):
                    if para.strip():
                        bld.add(type="paragraph", text=_clean(para), page=pno, source="ocr")
                continue
            if not any(k == "image" for _, _, k, _ in items):
                stats["scan_pages_without_ocr"].append(pno)
                iid = bld.save_image(png, "png", alt=f"Trang {pno} (bản scan, chưa OCR)")
                bld.images[iid].page, bld.images[iid].kind = pno, "page_scan"
                bld.add(type="image", text="", image_ids=[iid], page=pno, bbox=[0, 0, page.rect.width, h])
                continue

        # ---------------------------------------------------------------- emit in reading order
        items.sort(key=lambda it: (round(it[0] / 4), it[1]))
        for _, _, kind, p in items:
            bb = [round(float(v), 1) for v in p["bbox"]]
            if kind == "table":
                blk = bld.add_table(p["rows"], page=pno)
                blk.bbox = bb
                stats["tables"] += 1
            elif kind == "image":
                iid = bld.save_image(p["data"], p["ext"], size=p["size"])
                bld.images[iid].page, bld.images[iid].bbox, bld.images[iid].kind = pno, bb, "figure"
                bld.add(type="image", text="", image_ids=[iid], page=pno, bbox=bb)
                stats["images"] += 1
            else:
                text = p["text"]
                if p["level"]:
                    bld.add(type="heading", text=text, level=p["level"], page=pno, bbox=bb, source="text")
                    continue
                m = _BULLET.match(text)
                if m and len(p["lines"]) <= 3:
                    label = m.group(1) if m.group(1)[0].isalnum() else "•"
                    bld.add(type="list_item", text=text[m.end():], list_label=label, level=0, page=pno, bbox=bb,
                            source="text")
                else:
                    bld.add(type="paragraph", text=text, page=pno, bbox=bb, source="text")
    doc.close()
    _attach_captions(bld)
    return ParsedDocument(doc_id=doc_id, filename=filename, engine="local-pymupdf", blocks=bld.blocks,
                          images=bld.images, tables=bld.tables, meta=stats)


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


_CAPTION = re.compile(r"^(hinh|figure|fig\.|anh|so do|bieu do)\s*\d*")


def _attach_captions(bld: _Builder) -> None:
    """A short paragraph starting with Hình/Figure/Sơ đồ right after an image becomes its caption."""
    for i, b in enumerate(bld.blocks[:-1]):
        nxt = bld.blocks[i + 1]
        if b.type == "image" and b.image_ids and nxt.type == "paragraph" and \
                _CAPTION.match(_fold(nxt.text)) and len(nxt.text) < 200:
            img = bld.images.get(b.image_ids[0])
            if img and not img.alt:
                img.alt = nxt.text
            b.text = nxt.text


async def _ocr_png(png: bytes) -> str:
    from app.core.llm import LLMError, Part, llm
    try:
        res = await llm.complete("vision", system="Bạn là công cụ OCR. Chỉ trả về chữ đọc được trên ảnh, giữ xuống dòng giữa các đoạn, "
                                 "không giải thích. Bảng thì viết dạng markdown.",
                                 user=[Part(text="Trích toàn bộ chữ trên trang này."), Part.image(png, "image/png")],
                                 max_tokens=4096, temperature=0)
        return res.text.strip()
    except LLMError as e:
        logger.warning("OCR failed: %s", e)
        return ""


# =========================================================================== PPTX
EMU_PER_PT = 12700


def parse_pptx_local(file_bytes: bytes, filename: str, doc_id: str, data_dir: str, url_prefix: str) -> ParsedDocument:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(io.BytesIO(file_bytes))
    bld = _Builder(data_dir, url_prefix)
    seen: set = set()
    stats = {"slides": len(prs.slides), "tables": 0, "images": 0, "notes": 0,
             "slide_size_pt": [round((prs.slide_width or 0) / EMU_PER_PT, 1), round((prs.slide_height or 0) / EMU_PER_PT, 1)]}

    def bbox(sh) -> Optional[List[float]]:
        if sh.left is None or sh.top is None:
            return None
        return [round(sh.left / EMU_PER_PT, 1), round(sh.top / EMU_PER_PT, 1),
                round((sh.left + (sh.width or 0)) / EMU_PER_PT, 1), round((sh.top + (sh.height or 0)) / EMU_PER_PT, 1)]

    def walk(shapes):
        for sh in sorted(shapes, key=lambda s: ((s.top or 0), (s.left or 0))):
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                yield from walk(sh.shapes)
            else:
                yield sh

    for si, slide in enumerate(prs.slides, start=1):
        title_shape = slide.shapes.title
        title = _clean(title_shape.text_frame.text) if title_shape is not None and title_shape.has_text_frame else ""
        bld.add(type="heading", text=title or f"Slide {si}", level=1, page=si,
                bbox=bbox(title_shape) if title_shape is not None else None, source="text")
        for sh in walk(slide.shapes):
            if title_shape is not None and sh.shape_id == title_shape.shape_id:
                continue
            if getattr(sh, "has_table", False) and sh.has_table:
                rows = [[_clean(c.text) for c in r.cells] for r in sh.table.rows]
                if rows:
                    blk = bld.add_table(rows, page=si)
                    blk.bbox = bbox(sh)
                    stats["tables"] += 1
                continue
            image = None
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE or (hasattr(sh, "image") and sh.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER):
                try:
                    image = sh.image
                except Exception:
                    image = None
            if image is not None:
                digest = hashlib.sha1(image.blob).hexdigest()
                if digest not in seen:
                    seen.add(digest)
                    ext = (image.ext or "png").lower()
                    iid = bld.save_image(image.blob, ext, size=image.size if hasattr(image, "size") else None)
                    bld.images[iid].page, bld.images[iid].bbox, bld.images[iid].kind = si, bbox(sh), "slide_picture"
                    bld.add(type="image", text="", image_ids=[iid], page=si, bbox=bbox(sh))
                    stats["images"] += 1
                continue
            if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                paragraphs = sh.text_frame.paragraphs
                for para in paragraphs:
                    text = _clean(para.text)
                    if not text:
                        continue
                    if (para.level or 0) > 0 or len(paragraphs) > 1:
                        bld.add(type="list_item", text=text, list_label="•", level=int(para.level or 0), page=si,
                                bbox=bbox(sh), source="text")
                    else:
                        bld.add(type="paragraph", text=text, page=si, bbox=bbox(sh), source="text")
        if slide.has_notes_slide:
            notes = _clean(slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else "")
            if notes:
                bld.add(type="paragraph", text=notes, page=si, style="speaker_notes", source="notes")
                stats["notes"] += 1
    return ParsedDocument(doc_id=doc_id, filename=filename, engine="local-python-pptx", blocks=bld.blocks,
                          images=bld.images, tables=bld.tables, meta=stats)
