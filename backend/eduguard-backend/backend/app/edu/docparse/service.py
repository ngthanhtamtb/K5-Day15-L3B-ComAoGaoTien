"""Entry point for document ingestion: upload bytes -> ParsedDocument (+ chunks, markdown)."""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from app.core.config import settings
from app.edu import storage
from .docx_parser import DocxParser
from .local_parsers import parse_pdf_local, parse_pptx_local
from .models import Block, Chunk, ParsedDocument
from .other_parsers import convert_legacy_office, docling_available, parse_with_docling, parse_with_remote

logger = logging.getLogger(__name__)

SUPPORTED = {".docx", ".doc", ".pdf", ".pptx", ".ppt", ".md", ".txt"}


class UnsupportedDocument(ValueError):
    pass


async def ingest(file_bytes: bytes, filename: str, doc_id: Optional[str] = None) -> ParsedDocument:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED:
        raise UnsupportedDocument(f"Unsupported file type {ext}. Allowed: {', '.join(sorted(SUPPORTED))}")
    doc_id = doc_id or storage.new_id("doc")
    data_dir = os.path.dirname(storage.path("docs", doc_id, "x"))
    url_prefix = storage.url_for("docs", doc_id)

    if ext in (".doc", ".ppt"):
        target = "docx" if ext == ".doc" else "pptx"
        converted = convert_legacy_office(file_bytes, ext[1:], target)
        if converted is None:
            raise UnsupportedDocument(f"{ext} needs LibreOffice installed for conversion; please save as .{target}")
        file_bytes, ext, filename = converted, f".{target}", os.path.splitext(filename)[0] + f".{target}"

    if ext == ".docx":
        parsed = DocxParser(data_dir, url_prefix).parse(file_bytes, filename, doc_id)
    elif ext in (".md", ".txt"):
        from .other_parsers import _Builder, markdown_to_blocks
        bld = _Builder(data_dir, url_prefix)
        markdown_to_blocks(file_bytes.decode("utf-8", errors="replace"), bld)
        parsed = ParsedDocument(doc_id=doc_id, filename=filename, engine="markdown",
                                blocks=bld.blocks, images=bld.images, tables=bld.tables)
    else:  # pdf / pptx
        engine = (settings.EDU_PDF_ENGINE or "local").lower()
        if engine == "docling" or (engine == "auto" and docling_available()):
            parsed = parse_with_docling(file_bytes, filename, doc_id, data_dir, url_prefix)
        elif engine == "remote":
            if not settings.EXTRACT_DOC_API_URL:
                raise UnsupportedDocument("EDU_PDF_ENGINE=remote needs EXTRACT_DOC_API_URL")
            parsed = await parse_with_remote(file_bytes, filename, doc_id, data_dir, url_prefix)
        elif ext == ".pdf":
            parsed = await parse_pdf_local(file_bytes, filename, doc_id, data_dir, url_prefix)
        else:
            parsed = parse_pptx_local(file_bytes, filename, doc_id, data_dir, url_prefix)

    if settings.EDU_IMAGE_CAPTIONS:
        await caption_images(parsed, data_dir)
    parsed.markdown = to_markdown(parsed)
    parsed.chunks = build_chunks(parsed)
    with open(os.path.join(data_dir, "source" + ext), "wb") as fh:
        fh.write(file_bytes)
    storage.save_json(parsed.model_dump(), "docs", doc_id, "parsed.json")
    storage.save_json(summary(parsed), "docs", doc_id, "summary.json")   # cheap listing
    return parsed


async def caption_images(doc: ParsedDocument, data_dir: str, limit: int = 40) -> None:
    """Describe figures with the "vision" route so image content is searchable and citable.
    Runs only when EDU_IMAGE_CAPTIONS=true (costs one vision call per image, cached by hash)."""
    import hashlib
    from app.core.llm import LLMError, Part, llm
    for img in list(doc.images.values())[:limit]:
        if img.caption or img.kind == "page_scan" or not img.mime.startswith("image/") \
                or img.mime in ("image/x-wmf", "image/x-emf", "image/svg+xml"):
            continue
        try:
            with open(os.path.join(data_dir, img.path), "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        key = hashlib.sha1(data).hexdigest()
        cached = storage.load_json("captions", f"{key}.json")
        if cached:
            img.caption = cached.get("caption")
            continue
        try:
            res = await llm.complete("vision", system="Mô tả hình trong tài liệu học tập bằng 1–2 câu tiếng Việt: "
                                     "hình thể hiện gì, các nhãn / số liệu đọc được. Không suy đoán ngoài hình.",
                                     user=[Part(text=f"Chú thích có sẵn: {img.alt or '(không có)'}"),
                                           Part.image(data, img.mime)], max_tokens=300, temperature=0)
        except LLMError as e:
            logger.warning("caption failed for %s: %s", img.id, e)
            return                                   # provider down: stop, keep the doc usable
        img.caption = res.text.strip()
        storage.save_json({"caption": img.caption}, "captions", f"{key}.json")


def summary(doc: ParsedDocument) -> dict:
    import time
    headings = [b.text for b in doc.blocks if b.type == "heading"][:12]
    return {"docId": doc.doc_id, "filename": doc.filename, "engine": doc.engine, "createdAt": time.time(),
            "stats": {"blocks": len(doc.blocks), "images": len(doc.images), "tables": len(doc.tables),
                      "chunks": len(doc.chunks), "pages": doc.meta.get("pages") or doc.meta.get("slides")},
            "headings": headings}


def list_documents() -> List[dict]:
    root = os.path.join(storage.edu_root(), "docs")
    out = []
    for doc_id in os.listdir(root) if os.path.isdir(root) else []:
        s = storage.load_json("docs", doc_id, "summary.json")
        if s is None:                                   # documents ingested before summaries existed
            d = load(doc_id) if storage._SAFE_ID.match(doc_id) else None
            if d is None:
                continue
            s = summary(d)
            s["createdAt"] = os.path.getmtime(os.path.join(root, doc_id))
        out.append(s)
    return sorted(out, key=lambda s: -(s.get("createdAt") or 0))


def load(doc_id: str) -> Optional[ParsedDocument]:
    data = storage.load_json("docs", storage.check_id(doc_id), "parsed.json")
    return ParsedDocument(**data) if data else None


# --------------------------------------------------------------------------- markdown
def _block_md(b: Block, doc: ParsedDocument) -> str:
    if b.type == "table" and b.table:
        return b.table.markdown
    imgs = " ".join(
        f"![{doc.images[i].alt or i}]({doc.images[i].url})"
        + (f" *(Hình {i}: {doc.images[i].caption})*" if doc.images[i].caption else "")
        for i in b.image_ids if i in doc.images)
    text = b.full_text
    if b.source == "notes":
        return f"> Ghi chú người nói: {text}"
    if b.type == "heading":
        return f"{'#' * min(b.level or 1, 6)} {text}"
    if b.type == "list_item":
        indent = "  " * (b.level or 0)
        label = b.list_label or "-"
        label = "-" if label == "•" else label
        return f"{indent}{label} {b.text} {imgs}".rstrip()
    return f"{text} {imgs}".strip()


def to_markdown(doc: ParsedDocument) -> str:
    return "\n\n".join(filter(None, (_block_md(b, doc) for b in doc.blocks)))


# --------------------------------------------------------------------------- chunking
def build_chunks(doc: ParsedDocument, target_chars: int = 900) -> List[Chunk]:
    """Heading-aware chunks. A table or image never gets split from the text around it,
    so a quiz question generated from a chunk can still cite its figure/table."""
    chunks: List[Chunk] = []
    heading_path: List[str] = []
    cur_text: List[str] = []
    cur_blocks: List[str] = []
    cur_imgs: List[str] = []
    cur_tbls: List[str] = []
    cur_pages: List[int] = []
    prefix = doc.doc_id.split("_")[-1][:4].upper()

    def flush():
        text = "\n".join(t for t in cur_text if t).strip()
        if text or cur_imgs:
            chunks.append(Chunk(id=f"{prefix}-C{len(chunks) + 1:03d}", heading_path=list(heading_path),
                                text=text, block_ids=list(cur_blocks), image_ids=list(cur_imgs),
                                table_ids=list(cur_tbls), pages=sorted(set(cur_pages))))
        cur_text.clear(); cur_blocks.clear(); cur_imgs.clear(); cur_tbls.clear(); cur_pages.clear()

    for b in doc.blocks:
        if b.type == "heading":
            flush()
            lvl = b.level or 1
            heading_path[:] = heading_path[: lvl - 1] + [b.text]
            continue
        md = _block_md(b, doc)
        if sum(len(t) for t in cur_text) + len(md) > target_chars and cur_text and b.type not in ("table", "image"):
            flush()
        cur_text.append(md)
        cur_blocks.append(b.id)
        if b.page:
            cur_pages.append(b.page)
        cur_imgs.extend(b.image_ids)
        if b.table:
            cur_tbls.append(b.table.id)
            for c in b.table.cells:
                for cb in c.blocks:
                    cur_imgs.extend(cb.image_ids)
    flush()
    return chunks
