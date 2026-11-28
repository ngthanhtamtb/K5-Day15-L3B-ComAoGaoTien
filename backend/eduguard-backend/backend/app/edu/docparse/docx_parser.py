"""Native .docx parser (python-docx + lxml, no ML models).

Why not just pandoc / docling for Word files: Vietnamese exam files rely on things that generic
converters drop or flatten, and the quiz extractor needs all of them:
  * auto-numbering ("Câu %1." / "A." produced by Word lists, not typed text)
  * run formatting used as answer key (underlined / red / bold correct option)
  * options laid out in a 2x2 or 1x4 table, images inside table cells
  * MathType/WMF images and native OMML equations
  * text boxes and content controls

The walk follows document order exactly, so every image and table keeps its position.
"""
from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from docx import Document
from lxml import etree

from .models import Block, DocImage, DocTable, ParsedDocument, Span, TableCell

logger = logging.getLogger(__name__)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "o": "urn:schemas-microsoft-com:office:office",
}


def q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


W_VAL = q("w:val")
EMU_PER_PX = 9525
HEADING_RE = re.compile(r"^(heading|tiêu đề|title|tieu de)\s*(\d)?$", re.I)
MIME_BY_EXT = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
    "bmp": "image/bmp", "tif": "image/tiff", "tiff": "image/tiff", "svg": "image/svg+xml",
    "webp": "image/webp", "wmf": "image/x-wmf", "emf": "image/x-emf",
}


# --------------------------------------------------------------------------- numbering
def _roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _fmt(n: int, fmt: str) -> str:
    return {
        "decimal": str(n), "decimalZero": f"{n:02d}", "upperLetter": _letter(n),
        "lowerLetter": _letter(n).lower(), "upperRoman": _roman(n), "lowerRoman": _roman(n).lower(),
        "none": "",
    }.get(fmt, str(n))


class Numbering:
    """Renders Word auto-numbering labels such as 'Câu 3.' or 'B.'."""

    def __init__(self, doc):
        self.levels: Dict[str, Dict[int, Tuple[str, str, int]]] = {}   # abstractId -> ilvl -> (fmt, text, start)
        self.num_to_abs: Dict[str, str] = {}
        self.start_override: Dict[Tuple[str, int], int] = {}
        self.counters: Dict[str, Dict[int, int]] = {}
        try:
            root = doc.part.numbering_part.element
        except Exception:  # document without lists
            return
        for an in root.findall(q("w:abstractNum")):
            aid = an.get(q("w:abstractNumId"))
            lv = {}
            for l in an.findall(q("w:lvl")):
                ilvl = int(l.get(q("w:ilvl"), "0"))
                fmt_el, txt_el, st_el = l.find(q("w:numFmt")), l.find(q("w:lvlText")), l.find(q("w:start"))
                lv[ilvl] = (
                    fmt_el.get(W_VAL) if fmt_el is not None else "decimal",
                    txt_el.get(W_VAL) if txt_el is not None else "",
                    int(st_el.get(W_VAL)) if st_el is not None else 1,
                )
            self.levels[aid] = lv
        for num in root.findall(q("w:num")):
            nid = num.get(q("w:numId"))
            ab = num.find(q("w:abstractNumId"))
            if ab is not None:
                self.num_to_abs[nid] = ab.get(W_VAL)
            for ov in num.findall(q("w:lvlOverride")):
                so = ov.find(q("w:startOverride"))
                if so is not None:
                    self.start_override[(nid, int(ov.get(q("w:ilvl"), "0")))] = int(so.get(W_VAL))

    def label(self, num_id: str, ilvl: int) -> Optional[str]:
        aid = self.num_to_abs.get(num_id)
        if aid is None or num_id == "0":
            return None
        lv = self.levels.get(aid, {})
        if ilvl not in lv:
            return None
        cnt = self.counters.setdefault(num_id, {})
        fmt, text, start = lv[ilvl]
        start = self.start_override.get((num_id, ilvl), start)
        cnt[ilvl] = cnt.get(ilvl, start - 1) + 1
        for deeper in [k for k in cnt if k > ilvl]:
            del cnt[deeper]
        if fmt == "bullet":
            return "•"

        def repl(m):
            lvl = int(m.group(1)) - 1
            f, _, s = lv.get(lvl, ("decimal", "", 1))
            return _fmt(cnt.get(lvl, self.start_override.get((num_id, lvl), s)), f)

        return re.sub(r"%(\d)", repl, text).strip() or None


# --------------------------------------------------------------------------- OMML -> LaTeX
def omml_to_latex(el) -> str:
    """Small OMML→LaTeX converter covering what school material uses (fractions, powers,
    indices, roots, delimiters, n-ary operators). Unknown nodes fall back to their text."""

    def kids(e):
        return "".join(conv(c) for c in e)

    def part(e, name):
        c = e.find(q(f"m:{name}"))
        return kids(c) if c is not None else ""

    def conv(e) -> str:
        tag = etree.QName(e).localname if isinstance(e.tag, str) else ""
        if tag == "t":
            return e.text or ""
        if tag == "f":
            return f"\\frac{{{part(e, 'num')}}}{{{part(e, 'den')}}}"
        if tag == "sSup":
            return f"{{{part(e, 'e')}}}^{{{part(e, 'sup')}}}"
        if tag == "sSub":
            return f"{{{part(e, 'e')}}}_{{{part(e, 'sub')}}}"
        if tag == "sSubSup":
            return f"{{{part(e, 'e')}}}_{{{part(e, 'sub')}}}^{{{part(e, 'sup')}}}"
        if tag == "rad":
            deg = part(e, "deg")
            return f"\\sqrt[{deg}]{{{part(e, 'e')}}}" if deg else f"\\sqrt{{{part(e, 'e')}}}"
        if tag == "d":
            pr = e.find(q("m:dPr"))
            beg, end = "(", ")"
            if pr is not None:
                b, en = pr.find(q("m:begChr")), pr.find(q("m:endChr"))
                beg = b.get(q("m:val"), "(") if b is not None else "("
                end = en.get(q("m:val"), ")") if en is not None else ")"
            inner = ",".join(kids(x) for x in e.findall(q("m:e")))
            return f"\\left{beg or '.'}{inner}\\right{end or '.'}"
        if tag == "nary":
            pr = e.find(q("m:naryPr"))
            ch = "∫"
            if pr is not None and pr.find(q("m:chr")) is not None:
                ch = pr.find(q("m:chr")).get(q("m:val"), "∫")
            op = {"∑": "\\sum", "∏": "\\prod", "∫": "\\int", "∮": "\\oint"}.get(ch, ch)
            return f"{op}_{{{part(e, 'sub')}}}^{{{part(e, 'sup')}}}{{{part(e, 'e')}}}"
        if tag in ("rPr", "ctrlPr", "fPr", "radPr", "sSupPr", "sSubPr", "dPr", "naryPr", "oMathParaPr"):
            return ""
        return kids(e)

    return conv(el).strip()


# --------------------------------------------------------------------------- parser
class DocxParser:
    def __init__(self, data_dir: str, url_prefix: str):
        """data_dir: absolute folder for this document's assets; url_prefix: URL for that folder."""
        self.data_dir = data_dir
        self.url_prefix = url_prefix.rstrip("/")
        os.makedirs(os.path.join(data_dir, "images"), exist_ok=True)

    # ---------------------------------------------------------------- public
    def parse(self, file_bytes: bytes, filename: str, doc_id: str) -> ParsedDocument:
        self.doc = Document(io.BytesIO(file_bytes))
        self.part = self.doc.part
        self.numbering = Numbering(self.doc)
        self.order = 0
        self.page = 1
        self.images: Dict[str, DocImage] = {}
        self.tables: Dict[str, DocTable] = {}
        self._img_by_rid: Dict[str, str] = {}
        self._style_cache: Dict[str, dict] = {}

        blocks = self._parse_container(self.doc.element.body, in_table=None)
        return ParsedDocument(
            doc_id=doc_id, filename=filename, engine="docx-native",
            blocks=blocks, images=self.images, tables=self.tables,
            meta={"pages_estimated": self.page, "core_title": self.doc.core_properties.title or ""},
        )

    # ---------------------------------------------------------------- containers
    def _parse_container(self, container, in_table: Optional[str]) -> List[Block]:
        out: List[Block] = []
        for child in container:
            tag = child.tag
            if tag == q("w:p"):
                b = self._parse_paragraph(child, in_table)
                if b is not None:
                    out.append(b)
            elif tag == q("w:tbl"):
                out.append(self._parse_table(child, in_table))
            elif tag == q("w:sdt"):
                content = child.find(q("w:sdtContent"))
                if content is not None:
                    out.extend(self._parse_container(content, in_table))
            elif tag == q("mc:AlternateContent"):
                choice = child.find(q("mc:Choice"))
                if choice is not None:
                    out.extend(self._parse_container(choice, in_table))
        return out

    def _next_id(self) -> Tuple[str, int]:
        self.order += 1
        return f"b{self.order:04d}", self.order

    # ---------------------------------------------------------------- styles
    def _style_info(self, style_id: Optional[str]) -> dict:
        if not style_id:
            return {}
        if style_id in self._style_cache:
            return self._style_cache[style_id]
        info: dict = {}
        try:
            st = self.doc.styles.get_by_id(style_id, 1)  # WD_STYLE_TYPE.PARAGRAPH == 1
            info["name"] = st.name
            m = HEADING_RE.match((st.name or "").strip())
            if m:
                info["heading"] = int(m.group(2) or 1)
            ppr = st.element.pPr
            if ppr is not None:
                ol = ppr.find(q("w:outlineLvl"))
                if ol is not None and "heading" not in info:
                    lvl = int(ol.get(W_VAL))
                    if lvl < 9:
                        info["heading"] = lvl + 1
                npr = ppr.find(q("w:numPr"))
                if npr is not None:
                    nid = npr.find(q("w:numId"))
                    il = npr.find(q("w:ilvl"))
                    info["num"] = (nid.get(W_VAL) if nid is not None else None,
                                   int(il.get(W_VAL)) if il is not None else 0)
        except Exception:
            pass
        self._style_cache[style_id] = info
        return info

    # ---------------------------------------------------------------- paragraph
    def _parse_paragraph(self, p, in_table: Optional[str]) -> Optional[Block]:
        ppr = p.find(q("w:pPr"))
        style_id, heading, num = None, None, None
        if ppr is not None:
            ps = ppr.find(q("w:pStyle"))
            style_id = ps.get(W_VAL) if ps is not None else None
            ol = ppr.find(q("w:outlineLvl"))
            if ol is not None and int(ol.get(W_VAL)) < 9:
                heading = int(ol.get(W_VAL)) + 1
            npr = ppr.find(q("w:numPr"))
            if npr is not None:
                nid, il = npr.find(q("w:numId")), npr.find(q("w:ilvl"))
                num = (nid.get(W_VAL) if nid is not None else None, int(il.get(W_VAL)) if il is not None else 0)
        sinfo = self._style_info(style_id)
        heading = heading or sinfo.get("heading")
        num = num or sinfo.get("num")

        spans: List[Span] = []
        self._walk_inline(p, spans)
        spans = _merge_spans(spans)
        text = "".join(s.text for s in spans if s.text).strip()
        image_ids = [s.image_id for s in spans if s.image_id]
        has_eq = any(s.equation for s in spans)

        label = None
        if num and num[0]:
            label = self.numbering.label(num[0], num[1])

        if not text and not image_ids and not has_eq and not label:
            return None

        bid, order = self._next_id()
        if heading and text:
            btype, level = "heading", heading
        elif label:
            btype, level = "list_item", (num[1] if num else 0)
        elif image_ids and not text and not has_eq:
            btype, level = "image", None
        elif has_eq and not text.replace(" ", ""):
            btype, level = "equation", None
        else:
            btype, level = "paragraph", None
        if has_eq:  # put equations into text so downstream text consumers see them
            text = "".join(s.text if not s.equation else f"${s.equation}$" for s in spans).strip()
        return Block(id=bid, type=btype, order=order, text=text, level=level, list_label=label,
                     style=sinfo.get("name"), spans=spans, image_ids=image_ids,
                     page=self.page, in_table=in_table)

    def _walk_inline(self, el, spans: List[Span], fmt: Optional[dict] = None):
        for child in el:
            tag = child.tag
            if tag == q("w:r"):
                self._parse_run(child, spans)
            elif tag in (q("w:del"), q("w:moveFrom"), q("w:pPr"), q("w:rPr")):
                continue
            elif tag in (q("m:oMath"), q("m:oMathPara")):
                spans.append(Span(text="", equation=omml_to_latex(child)))
            elif tag == q("mc:AlternateContent"):
                choice = child.find(q("mc:Choice"))
                if choice is not None:
                    self._walk_inline(choice, spans)
            else:  # hyperlink, ins, smartTag, sdt/sdtContent, fldSimple, bookmarks...
                self._walk_inline(child, spans)

    def _run_format(self, r) -> dict:
        rpr = r.find(q("w:rPr"))
        f = {"bold": False, "italic": False, "underline": False, "color": None, "highlight": None}
        if rpr is None:
            return f

        def on(tag):
            e = rpr.find(q(tag))
            return e is not None and e.get(W_VAL, "true") not in ("0", "false", "none")

        f["bold"], f["italic"], f["underline"] = on("w:b"), on("w:i"), on("w:u")
        c = rpr.find(q("w:color"))
        if c is not None and c.get(W_VAL) not in (None, "auto", "000000"):
            f["color"] = c.get(W_VAL).upper()
        h = rpr.find(q("w:highlight"))
        if h is not None and h.get(W_VAL) not in (None, "none"):
            f["highlight"] = h.get(W_VAL)
        shd = rpr.find(q("w:shd"))
        if f["highlight"] is None and shd is not None and shd.get(q("w:fill")) not in (None, "auto", "FFFFFF"):
            f["highlight"] = shd.get(q("w:fill"))
        return f

    def _parse_run(self, r, spans: List[Span]):
        f = self._run_format(r)
        buf: List[str] = []

        def flush():
            if buf:
                spans.append(Span(text="".join(buf), **f))
                buf.clear()

        for c in r:
            tag = c.tag
            if tag == q("w:t"):
                buf.append(c.text or "")
            elif tag == q("w:tab"):
                buf.append("\t")
            elif tag in (q("w:br"), q("w:cr")):
                if c.get(q("w:type")) == "page":
                    self.page += 1
                else:
                    buf.append("\n")
            elif tag == q("w:lastRenderedPageBreak"):
                self.page += 1
            elif tag == q("w:noBreakHyphen"):
                buf.append("-")
            elif tag == q("w:sym"):
                ch = c.get(q("w:char"))
                if ch:
                    try:
                        code = int(ch, 16)
                        buf.append(chr(code - 0xF000 if code >= 0xF000 else code))  # symbol-font private range
                    except ValueError:
                        pass
            elif tag in (q("w:drawing"), q("w:pict"), q("w:object"), q("mc:AlternateContent")):
                flush()
                self._parse_graphic(c, spans)
        flush()

    # ---------------------------------------------------------------- images / text boxes
    def _iter_no_fallback(self, el):
        """Descendants of el, skipping mc:Fallback (it duplicates mc:Choice)."""
        stack = [el]
        while stack:
            cur = stack.pop()
            yield cur
            for ch in reversed(list(cur)):
                if ch.tag == q("mc:Fallback"):
                    continue
                stack.append(ch)

    def _parse_graphic(self, el, spans: List[Span]):
        extent = None
        alt = None
        for d in self._iter_no_fallback(el):
            tag = d.tag
            if tag == q("wp:extent"):
                extent = (int(d.get("cx", 0)) // EMU_PER_PX, int(d.get("cy", 0)) // EMU_PER_PX)
            elif tag == q("wp:docPr"):
                alt = d.get("descr") or d.get("title") or None
            elif tag == q("a:blip"):
                rid = d.get(q("r:embed")) or d.get(q("r:link"))
                img_id = self._save_image(rid, extent, alt)
                if img_id:
                    spans.append(Span(text="", image_id=img_id))
            elif tag == q("v:imagedata"):
                rid = d.get(q("r:id")) or d.get(q("o:relid"))
                img_id = self._save_image(rid, extent, alt or d.get(q("o:title")))
                if img_id:
                    spans.append(Span(text="", image_id=img_id))
            elif tag == q("w:txbxContent"):
                # text box: keep its text inline (exams sometimes put stems in text boxes)
                for p in d.findall(q("w:p")):
                    inner: List[Span] = []
                    self._walk_inline(p, inner)
                    t = "".join(s.text for s in inner).strip()
                    if t:
                        spans.append(Span(text=("\n" + t), bold=False))
                    spans.extend(s for s in inner if s.image_id)

    def _save_image(self, rid: Optional[str], extent, alt) -> Optional[str]:
        if not rid:
            return None
        if rid in self._img_by_rid:  # same picture reused → new placement, same file
            return self._img_by_rid[rid]
        try:
            part = self.part.related_parts[rid]
        except KeyError:
            return None
        blob = getattr(part, "blob", None)
        if not blob:
            return None
        ext = os.path.splitext(str(part.partname))[1].lstrip(".").lower() or "png"
        img_id = f"img{len(self.images) + 1:03d}"
        converted_from = None
        if ext in ("wmf", "emf"):
            png = _rasterise_vector(blob, ext)
            if png:
                blob, converted_from, ext = png, ext, "png"
        fname = f"{img_id}.{ext}"
        with open(os.path.join(self.data_dir, "images", fname), "wb") as fh:
            fh.write(blob)
        w, h = (extent or (None, None))
        if w is None:
            try:
                from PIL import Image
                with Image.open(io.BytesIO(blob)) as im:
                    w, h = im.size
            except Exception:
                pass
        self.images[img_id] = DocImage(
            id=img_id, path=f"images/{fname}", url=f"{self.url_prefix}/images/{fname}",
            mime=MIME_BY_EXT.get(ext, "application/octet-stream"),
            width_px=w, height_px=h, alt=alt, converted_from=converted_from,
        )
        self._img_by_rid[rid] = img_id
        return img_id

    # ---------------------------------------------------------------- tables
    def _parse_table(self, tbl, in_table: Optional[str]) -> Block:
        tid = f"tbl{len(self.tables) + 1:02d}"
        self.tables[tid] = None  # reserve id so nested tables get the next number
        bid, order = self._next_id()
        cells: List[TableCell] = []
        origin: Dict[int, TableCell] = {}  # col -> cell that started a vertical merge
        n_cols = 0
        rows = tbl.findall(q("w:tr"))
        for ri, tr in enumerate(rows):
            col = 0
            trpr = tr.find(q("w:trPr"))
            if trpr is not None:
                gb = trpr.find(q("w:gridBefore"))
                if gb is not None:
                    col += int(gb.get(W_VAL, "0"))
            for tc in tr.findall(q("w:tc")):
                tcpr = tc.find(q("w:tcPr"))
                span, vmerge = 1, None
                if tcpr is not None:
                    gs = tcpr.find(q("w:gridSpan"))
                    if gs is not None:
                        span = int(gs.get(W_VAL, "1"))
                    vm = tcpr.find(q("w:vMerge"))
                    if vm is not None:
                        vmerge = vm.get(W_VAL, "continue")
                if vmerge == "continue" and col in origin:
                    origin[col].rowspan += 1
                    col += span
                    continue
                cell_blocks = self._parse_container(tc, in_table=tid)
                text = "\n".join(b.full_text if b.type != "table" else (b.table.markdown if b.table else "")
                                 for b in cell_blocks).strip()
                cell = TableCell(text=text, row=ri, col=col, colspan=span, blocks=cell_blocks)
                cells.append(cell)
                if vmerge == "restart":
                    origin[col] = cell
                else:
                    origin.pop(col, None)
                col += span
            n_cols = max(n_cols, col)
        table = DocTable(id=tid, n_rows=len(rows), n_cols=n_cols, cells=cells,
                         markdown="", html="")
        table.html = table_to_html(table, self.images)
        table.markdown = table_to_markdown(table, self.images)
        self.tables[tid] = table
        return Block(id=bid, type="table", order=order, text=table.markdown, table=table,
                     page=self.page, in_table=in_table)


# --------------------------------------------------------------------------- helpers
def _merge_spans(spans: List[Span]) -> List[Span]:
    out: List[Span] = []
    for s in spans:
        if (out and not s.image_id and not s.equation and not out[-1].image_id and not out[-1].equation
                and (s.bold, s.italic, s.underline, s.color, s.highlight) ==
                (out[-1].bold, out[-1].italic, out[-1].underline, out[-1].color, out[-1].highlight)):
            out[-1] = out[-1].model_copy(update={"text": out[-1].text + s.text})
        else:
            out.append(s)
    return out


def _cell_inline_md(cell: TableCell, images: Dict[str, DocImage]) -> str:
    parts = []
    for b in cell.blocks:
        t = b.full_text
        for iid in b.image_ids:
            if iid in images:
                t += f" ![{images[iid].alt or iid}]({images[iid].url})"
        parts.append(t.strip())
    return "<br>".join(p.replace("|", "\\|") for p in parts if p)


def table_to_markdown(t: DocTable, images: Dict[str, DocImage]) -> str:
    if any(c.rowspan > 1 or c.colspan > 1 for c in t.cells) or any(
            b.type == "table" for c in t.cells for b in c.blocks):
        return t.html  # markdown can't express merges; HTML is valid inside markdown
    grid = [["" for _ in range(t.n_cols)] for _ in range(t.n_rows)]
    for c in t.cells:
        if c.row < t.n_rows and c.col < t.n_cols:
            grid[c.row][c.col] = _cell_inline_md(c, images)
    if not grid:
        return ""
    lines = ["| " + " | ".join(grid[0]) + " |", "|" + "---|" * t.n_cols]
    lines += ["| " + " | ".join(r) + " |" for r in grid[1:]]
    return "\n".join(lines)


def table_to_html(t: DocTable, images: Dict[str, DocImage]) -> str:
    from html import escape
    rows: Dict[int, List[str]] = {}
    for c in t.cells:
        inner = []
        for b in c.blocks:
            if b.type == "table" and b.table:
                inner.append(b.table.html)
                continue
            seg = escape(b.full_text)
            for iid in b.image_ids:
                if iid in images:
                    seg += f'<img src="{images[iid].url}" alt="{escape(images[iid].alt or iid)}"/>'
            inner.append(seg)
        attrs = (f' rowspan="{c.rowspan}"' if c.rowspan > 1 else "") + (f' colspan="{c.colspan}"' if c.colspan > 1 else "")
        rows.setdefault(c.row, []).append(f"<td{attrs}>{'<br/>'.join(inner)}</td>")
    body = "".join(f"<tr>{''.join(rows.get(i, []))}</tr>" for i in range(t.n_rows))
    return f'<table data-table-id="{t.id}">{body}</table>'


def _rasterise_vector(blob: bytes, ext: str) -> Optional[bytes]:
    """WMF/EMF (MathType equations, old clip-art) can't be shown in browsers.
    Pillow renders them on Windows; elsewhere we try LibreOffice. Returns PNG bytes or None."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(blob)) as im:
            try:
                im.load(dpi=200)  # WMF/EMF plugin accepts a render dpi
            except TypeError:
                im.load()
            out = io.BytesIO()
            im.save(out, "PNG")
            return out.getvalue()
    except Exception:
        pass
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, f"in.{ext}")
            with open(src, "wb") as fh:
                fh.write(blob)
            subprocess.run([soffice, "--headless", "--convert-to", "png", "--outdir", tmp, src],
                           capture_output=True, timeout=60)
            dst = os.path.join(tmp, "in.png")
            if os.path.exists(dst):
                with open(dst, "rb") as fh:
                    return fh.read()
    except Exception as e:  # pragma: no cover
        logger.warning("vector image conversion failed: %s", e)
    return None
