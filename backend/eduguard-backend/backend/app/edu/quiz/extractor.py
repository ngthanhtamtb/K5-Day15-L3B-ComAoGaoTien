"""Pull existing questions out of a parsed exam/worksheet.

Handles the layouts teachers actually use:
  * "Câu 1." typed or produced by Word auto-numbering, stems spanning several paragraphs
  * options on one line separated by tabs/spaces, one per line, auto-numbered A./B., or in a table
  * images/tables/equations in the stem or as an option
  * answers marked by underline / red / highlight / bold, by an "Đáp án: B" line, or by an
    answer-key table at the end ("1 2 3 / B A C" or "1-B, 2-A")
  * new-format exams: Phần I (MCQ), Phần II (Đúng/Sai with a) b) c) d)), Phần III (trả lời ngắn)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.edu.docparse.models import Block, ParsedDocument, Span
from .schemas import QuizOption, QuizQuestion, SourceRef

Q_START = re.compile(r"^\s*(?:Câu|Cau|Question)\s*(\d+)\s*[.:)\-]?\s*", re.I)
ANSWER_LINE = re.compile(r"^\s*(?:Đáp án|Dap an|Chọn|Answer|ĐA)\s*(?:đúng)?\s*[:.]?\s*(.+)$", re.I)
EXPLAIN_LINE = re.compile(r"^\s*(?:Lời giải|Giải thích|Hướng dẫn(?: giải)?|HDG|HD|Giải)\s*[:.]?\s*", re.I)
SECTION_LINE = re.compile(r"^\s*(?:PHẦN|Phần)\s+([IVX\d]+)", re.I)
KEY_HEADING = re.compile(r"^\s*(?:BẢNG\s+)?ĐÁP\s*ÁN\b", re.I)
MARKER = re.compile(r"(?<![\w])([A-Ha-h])\s*[.)]\s*")
KEY_PAIR = re.compile(r"(\d+)\s*[-.:)]\s*([A-HĐSđs]+|[\d,.\-]+)")
RED_HEX = re.compile(r"^(?:[C-F][0-9A-F])[0-4][0-9A-F][0-4][0-9A-F]$")  # strong red, low G/B


@dataclass
class _Line:
    raw: str                     # concatenated span text (no auto-number label)
    label: Optional[str]         # auto-number label, e.g. "B."
    spans: List[Span]
    image_ids: List[str]
    block: Block

    @property
    def text(self) -> str:
        return (f"{self.label} {self.raw}" if self.label else self.raw).strip()


@dataclass
class _Q:
    number: int
    section: Optional[str]
    stem_parts: List[str] = field(default_factory=list)
    stem_images: List[str] = field(default_factory=list)
    stem_tables: List[str] = field(default_factory=list)
    options: List[dict] = field(default_factory=list)  # {key, text, images, marks}
    inline_answer: Optional[str] = None
    explanation: List[str] = field(default_factory=list)
    mode: str = "stem"           # stem | options | explain
    blocks: List[Block] = field(default_factory=list)


def _line_from_block(b: Block) -> _Line:
    raw = "".join(s.text if not s.equation else f"${s.equation}$" for s in b.spans) if b.spans else b.text
    return _Line(raw=raw, label=b.list_label, spans=b.spans, image_ids=list(b.image_ids), block=b)


def _marks(spans: List[Span], start: int, end: int) -> set:
    """Formatting marks covering [start, end) of the concatenated span text."""
    found, pos = set(), 0
    for s in spans:
        t = s.text if not s.equation else f"${s.equation}$"
        s_start, s_end = pos, pos + len(t)
        pos = s_end
        if s_end <= start or s_start >= end or not t.strip():
            continue
        if s.underline:
            found.add("underline")
        if s.color and RED_HEX.match(s.color):
            found.add("color")
        if s.highlight:
            found.add("highlight")
        if s.bold:
            found.add("bold")
    return found


def split_options(line: _Line) -> List[dict]:
    """Split one line into options. Markers must appear in order (A,B,C,D...) so that
    'Vitamin A. ...' inside an option is not mistaken for a new option."""
    opts: List[dict] = []
    raw = line.raw
    if line.label and re.fullmatch(r"[A-Ha-h][.)]", line.label.strip()):
        key = line.label.strip()[0]
        return [{"key": key, "text": raw.strip(), "images": list(line.image_ids),
                 "marks": _marks(line.spans, 0, len(raw))}]
    accepted: List[re.Match] = []
    for m in MARKER.finditer(raw):
        letter = m.group(1)
        if not accepted:
            if raw[: m.start()].strip():
                break  # line doesn't start with a marker -> not an option line
            accepted.append(m)
            continue
        expected = chr(ord(accepted[-1].group(1)) + 1)
        if letter == expected and raw[m.start() - 1] in " \t\n":
            accepted.append(m)
    for i, m in enumerate(accepted):
        start = m.end()
        end = accepted[i + 1].start() if i + 1 < len(accepted) else len(raw)
        opts.append({"key": m.group(1), "text": raw[start:end].strip(" \t;"),
                     "images": [], "marks": _marks(line.spans, m.start(), end)})
    if opts and line.image_ids:
        opts[-1]["images"].extend(line.image_ids)
    return opts


def _decide_marked(options: List[dict]) -> Tuple[Optional[str], Optional[str]]:
    """Pick the option distinguished by formatting. Bold only counts when it is unique."""
    for mark in ("underline", "color", "highlight", "bold"):
        hits = [o["key"] for o in options if mark in o["marks"]]
        if len(hits) == 1 and len(options) > 1:
            return hits[0], mark
    return None, None


def _parse_key_text(text: str) -> Dict[int, str]:
    return {int(n): a.strip() for n, a in KEY_PAIR.findall(text)}


def _parse_key_table(block: Block) -> Dict[int, str]:
    t = block.table
    grid: Dict[Tuple[int, int], str] = {(c.row, c.col): c.text.strip() for c in t.cells}
    key: Dict[int, str] = {}
    # pattern 1: number row followed by answer row (repeated)
    for r in range(t.n_rows - 1):
        row = [grid.get((r, c), "") for c in range(t.n_cols)]
        nxt = [grid.get((r + 1, c), "") for c in range(t.n_cols)]
        if sum(x.isdigit() for x in row) >= max(1, len([x for x in row if x]) - 1):
            for n, a in zip(row, nxt):
                if n.isdigit() and a:
                    key[int(n)] = a
    # pattern 2: two columns "1 | B"
    if not key and t.n_cols >= 2:
        for r in range(t.n_rows):
            for c in range(0, t.n_cols - 1, 2):
                n, a = grid.get((r, c), ""), grid.get((r, c + 1), "")
                if n.isdigit() and a:
                    key[int(n)] = a
    # pattern 3: "1-B" inside cells
    if not key:
        for v in grid.values():
            key.update(_parse_key_text(v))
    return key


def extract_questions(doc: ParsedDocument, code_prefix: Optional[str] = None) -> Tuple[List[QuizQuestion], List[str]]:
    warnings: List[str] = []
    prefix = code_prefix or doc.doc_id.split("_")[-1][:4].upper()
    questions: List[_Q] = []
    cur: Optional[_Q] = None
    section: Optional[str] = None
    in_key = False
    answer_key: Dict[int, str] = {}

    def handle_line(line: _Line):
        nonlocal cur, section, in_key
        text = line.text
        if not text and not line.image_ids:
            return
        if in_key:
            answer_key.update(_parse_key_text(text))
            return
        sm = SECTION_LINE.match(text)
        if sm and not Q_START.match(text):
            section = text.strip()
            return
        qm = Q_START.match(text)
        if qm:
            cur = _Q(number=int(qm.group(1)), section=section)
            questions.append(cur)
            rest_raw = text[qm.end():]
            # options can follow the stem on the same line: "Câu 1. ... A. x B. y"
            cur.stem_parts.append(rest_raw.strip())
            cur.stem_images.extend(line.image_ids)
            cur.blocks.append(line.block)
            return
        if cur is None:
            return
        cur.blocks.append(line.block)
        am = ANSWER_LINE.match(text)
        if am:
            cur.inline_answer = am.group(1).strip()
            return
        if EXPLAIN_LINE.match(text):
            cur.mode = "explain"
            cur.explanation.append(EXPLAIN_LINE.sub("", text, count=1).strip())
            return
        if cur.mode == "explain":
            cur.explanation.append(text)
            return
        opts = split_options(line)
        if opts:
            cur.options.extend(opts)
            cur.mode = "options"
            return
        if not text.strip() and line.image_ids:  # picture-only paragraph
            if cur.mode == "options" and cur.options and not cur.options[-1]["text"]:
                cur.options[-1]["images"].extend(line.image_ids)
            else:
                cur.stem_images.extend(line.image_ids)
            return
        if cur.mode == "stem":
            cur.stem_parts.append(text)
            cur.stem_images.extend(line.image_ids)
        elif cur.options:
            cur.options[-1]["text"] = (cur.options[-1]["text"] + " " + text).strip()

    for b in doc.blocks:
        if b.type == "heading":
            if KEY_HEADING.match(b.text):
                in_key = True
                continue
            if SECTION_LINE.match(b.text):
                section, in_key = b.text.strip(), False
                continue
            if Q_START.match(b.full_text):
                handle_line(_line_from_block(b))
            continue
        if b.type == "table" and b.table:
            if in_key:
                answer_key.update(_parse_key_table(b))
                continue
            cell_lines = [_line_from_block(cb) for c in sorted(b.table.cells, key=lambda c: (c.row, c.col))
                          for cb in c.blocks if cb.type != "table"]
            is_option_table = cur is not None and cell_lines and all(
                split_options(ln) or not ln.text.strip() for ln in cell_lines)
            if is_option_table:
                for ln in cell_lines:
                    handle_line(ln)
            elif cur is not None and cur.mode == "stem":
                cur.stem_tables.append(b.table.id)
                cur.blocks.append(b)
            elif cur is None and _parse_key_table(b) and len(_parse_key_table(b)) >= 3:
                answer_key.update(_parse_key_table(b))
            continue
        if KEY_HEADING.match(b.full_text) and len(b.full_text) < 40:
            in_key = True
            rest = KEY_HEADING.sub("", b.full_text)
            answer_key.update(_parse_key_text(rest))
            continue
        handle_line(_line_from_block(b))

    # ------------------------------------------------------------------ finalise
    out: List[QuizQuestion] = []
    seen_numbers: Dict[str, int] = {}
    for q in questions:
        stem = " ".join(p for p in q.stem_parts if p).strip()
        lower = bool(q.options) and all(o["key"].islower() for o in q.options)
        qtype = "true_false" if lower else ("mcq" if q.options else "short_answer")
        # options embedded in the stem line
        if not q.options:
            for mm in re.finditer(r"\sA\s*[.)]\s", " " + stem):
                cut = mm.start()
                tail = _Line(raw=stem[cut:].strip(), label=None, spans=[], image_ids=[], block=q.blocks[0])
                opts = split_options(tail)
                if len(opts) >= 2:
                    stem = stem[:cut].strip()
                    q.options = opts
                    qtype = "mcq"
                break

        correct_key, answer_text, detected = None, None, None
        key_val = answer_key.get(q.number)
        if qtype == "mcq":
            if key_val and re.fullmatch(r"[A-H]", key_val.strip().upper()):
                correct_key, detected = key_val.strip().upper(), "key_table"
            elif q.inline_answer and re.match(r"^[A-H]\b", q.inline_answer.upper()):
                correct_key, detected = q.inline_answer.upper()[0], "inline"
            else:
                correct_key, detected = _decide_marked(q.options)
        tf_truth: Dict[str, bool] = {}
        if qtype == "true_false":
            src = key_val or q.inline_answer or ""
            letters = re.findall(r"[ĐSđs]", src)
            if len(letters) == len(q.options):
                tf_truth = {o["key"]: l.upper() == "Đ" for o, l in zip(q.options, letters)}
                detected = "key_table" if key_val else "inline"
        if qtype == "short_answer":
            answer_text = key_val or q.inline_answer
            detected = ("key_table" if key_val else "inline") if answer_text else None

        options = [QuizOption(key=o["key"], text=o["text"], image_ids=o["images"],
                              is_correct=(tf_truth.get(o["key"]) if qtype == "true_false"
                                          else (o["key"] == correct_key if correct_key else None)))
                   for o in q.options]

        sec_key = q.section or ""
        if seen_numbers.get(f"{sec_key}|{q.number}"):
            warnings.append(f"Câu {q.number} bị trùng số trong cùng phần — kiểm tra lại đánh số.")
        seen_numbers[f"{sec_key}|{q.number}"] = 1
        if qtype == "mcq" and not correct_key:
            warnings.append(f"Câu {q.number}: không xác định được đáp án đúng (không có bảng đáp án / gạch chân / tô màu).")
        if qtype == "mcq" and len(options) < 2:
            warnings.append(f"Câu {q.number}: chỉ tìm thấy {len(options)} phương án.")

        idx = len(out) + 1
        first_block = q.blocks[0] if q.blocks else None
        out.append(QuizQuestion(
            id=f"q{idx:03d}", code=f"{prefix}-Q{idx:02d}", number=q.number, type=qtype,
            section=q.section, stem=stem, stem_image_ids=q.stem_images, stem_table_ids=q.stem_tables,
            options=options, correct_key=correct_key, answer_text=answer_text,
            explanation=" ".join(e for e in q.explanation if e).strip(), answer_detected_by=detected,
            source=SourceRef(doc_id=doc.doc_id, page=first_block.page if first_block else None),
            origin="extracted",
        ))
    return out, warnings
