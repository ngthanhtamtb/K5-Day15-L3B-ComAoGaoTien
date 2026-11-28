"""PDF / PPTX / legacy formats.

Engine order (EDU_PDF_ENGINE=auto):
  1. docling installed locally  -> layout model, tables, figures with page numbers
  2. RAGslides' existing remote extractor (settings.EXTRACT_DOC_API_URL, a docling-serve endpoint)
Both are normalised into the same ParsedDocument as the native docx parser.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from .models import Block, DocImage, DocTable, ParsedDocument, TableCell

logger = logging.getLogger(__name__)


def docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except Exception:
        return False


def convert_legacy_office(file_bytes: bytes, ext: str, target: str) -> Optional[bytes]:
    """.doc -> .docx, .ppt -> .pptx via LibreOffice if installed."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f"in.{ext}")
        with open(src, "wb") as fh:
            fh.write(file_bytes)
        subprocess.run([soffice, "--headless", "--convert-to", target, "--outdir", tmp, src],
                       capture_output=True, timeout=180)
        dst = os.path.join(tmp, f"in.{target}")
        if os.path.exists(dst):
            with open(dst, "rb") as fh:
                return fh.read()
    return None


class _Builder:
    """Accumulates blocks/images/tables while normalising foreign formats."""

    def __init__(self, data_dir: str, url_prefix: str):
        self.data_dir, self.url_prefix = data_dir, url_prefix.rstrip("/")
        os.makedirs(os.path.join(data_dir, "images"), exist_ok=True)
        self.blocks: List[Block] = []
        self.images: Dict[str, DocImage] = {}
        self.tables: Dict[str, DocTable] = {}

    def add(self, **kw) -> Block:
        n = len(self.blocks) + 1
        b = Block(id=f"b{n:04d}", order=n, **kw)
        self.blocks.append(b)
        return b

    def save_image(self, data: bytes, ext: str = "png", alt: Optional[str] = None,
                   size: Optional[tuple] = None) -> str:
        iid = f"img{len(self.images) + 1:03d}"
        fname = f"{iid}.{ext}"
        with open(os.path.join(self.data_dir, "images", fname), "wb") as fh:
            fh.write(data)
        w, h = size or (None, None)
        self.images[iid] = DocImage(id=iid, path=f"images/{fname}", url=f"{self.url_prefix}/images/{fname}",
                                    mime=f"image/{'jpeg' if ext == 'jpg' else ext}", width_px=w, height_px=h, alt=alt)
        return iid

    def add_table(self, rows: List[List[str]], html: Optional[str] = None, page: Optional[int] = None) -> Block:
        tid = f"tbl{len(self.tables) + 1:02d}"
        n_cols = max((len(r) for r in rows), default=0)
        cells = [TableCell(text=c, row=ri, col=ci) for ri, r in enumerate(rows) for ci, c in enumerate(r)]
        md = ""
        if rows:
            md = "\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * n_cols] +
                           ["| " + " | ".join(r) + " |" for r in rows[1:]])
        from html import escape
        html = html or "<table>" + "".join(
            "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>"
        t = DocTable(id=tid, n_rows=len(rows), n_cols=n_cols, cells=cells, markdown=md, html=html)
        self.tables[tid] = t
        return self.add(type="table", text=md, table=t, page=page)


# --------------------------------------------------------------------------- docling (local)
def parse_with_docling(file_bytes: bytes, filename: str, doc_id: str, data_dir: str, url_prefix: str) -> ParsedDocument:
    from docling.datamodel.base_models import InputFormat, DocumentStream
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.generate_picture_images = True
    opts.images_scale = 2.0
    opts.do_table_structure = True
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    result = converter.convert(DocumentStream(name=filename, stream=io.BytesIO(file_bytes)))
    doc = result.document

    bld = _Builder(data_dir, url_prefix)
    for item, level in doc.iterate_items():
        cls = type(item).__name__
        page = item.prov[0].page_no if getattr(item, "prov", None) else None
        label = str(getattr(item, "label", "")).split(".")[-1].lower()
        if cls == "TableItem":
            try:
                df = item.export_to_dataframe(doc)
                rows = [list(map(str, df.columns))] + [[str(x) for x in r] for r in df.values.tolist()]
            except Exception:
                rows = []
            html = item.export_to_html(doc) if hasattr(item, "export_to_html") else None
            bld.add_table(rows, html=html, page=page)
        elif cls == "PictureItem":
            img = item.get_image(doc)
            if img is None:
                continue
            buf = io.BytesIO()
            img.save(buf, "PNG")
            cap = item.caption_text(doc) if hasattr(item, "caption_text") else None
            iid = bld.save_image(buf.getvalue(), "png", alt=cap, size=img.size)
            bld.add(type="image", text=cap or "", image_ids=[iid], page=page)
        else:
            text = getattr(item, "text", "") or ""
            if not text.strip():
                continue
            if label in ("title", "section_header"):
                bld.add(type="heading", text=text, level=1 if label == "title" else max(level, 1), page=page)
            elif label == "list_item":
                marker = getattr(item, "marker", None)
                bld.add(type="list_item", text=text, list_label=marker or None, level=0, page=page)
            elif label == "formula":
                bld.add(type="equation", text=f"${text}$", page=page)
            elif label in ("page_header", "page_footer"):
                continue
            else:
                bld.add(type="paragraph", text=text, page=page)
    return ParsedDocument(doc_id=doc_id, filename=filename, engine="docling", blocks=bld.blocks,
                          images=bld.images, tables=bld.tables,
                          meta={"pages": len(getattr(doc, "pages", {}) or {})})


# --------------------------------------------------------------------------- remote (RAGslides extractor)
async def parse_with_remote(file_bytes: bytes, filename: str, doc_id: str, data_dir: str, url_prefix: str) -> ParsedDocument:
    ext = os.path.splitext(filename)[1].lower()
    mime = {".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(ext, "application/octet-stream")
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(settings.EXTRACT_DOC_API_URL, headers={"accept": "application/json"},
                                 files={"document": (filename, file_bytes, mime)},
                                 data={"extract_tables_as_images": "false", "image_resolution_scale": "2"})
        resp.raise_for_status()
        payload = resp.json()
    md = _find_markdown(payload)
    bld = _Builder(data_dir, url_prefix)
    markdown_to_blocks(md, bld)
    return ParsedDocument(doc_id=doc_id, filename=filename, engine="remote-docling", blocks=bld.blocks,
                          images=bld.images, tables=bld.tables)


def _find_markdown(payload) -> str:
    """docling-serve style payloads differ by version; look for the markdown string anywhere."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("md_content", "markdown", "md", "content", "text"):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                return v
        for v in payload.values():
            found = _find_markdown(v)
            if found:
                return found
    if isinstance(payload, list):
        return "\n\n".join(filter(None, (_find_markdown(x) for x in payload)))
    return ""


IMG_MD = re.compile(r"!\[([^\]]*)\]\((data:image/(\w+);base64,([A-Za-z0-9+/=]+)|[^)]+)\)")


def markdown_to_blocks(md: str, bld: _Builder) -> None:
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            bld.add_table(rows)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            bld.add(type="heading", text=m.group(2).strip(), level=len(m.group(1)))
            i += 1
            continue
        image_ids = []
        for im in IMG_MD.finditer(line):
            if im.group(4):
                image_ids.append(bld.save_image(base64.b64decode(im.group(4)), im.group(3), alt=im.group(1) or None))
        text = IMG_MD.sub("", line).strip()
        lm = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)", text)
        if lm:
            bld.add(type="list_item", text=lm.group(2), list_label=lm.group(1) if lm.group(1)[0].isdigit() else "•",
                    level=0, image_ids=image_ids)
        elif text or image_ids:
            bld.add(type="image" if image_ids and not text else "paragraph", text=text, image_ids=image_ids)
        i += 1
