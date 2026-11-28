"""Structured quiz PDF for teachers: exam paper and answer key (key + explanation + source).

Every question except the ones the teacher dropped is printed.
Needs a Unicode TTF for Vietnamese: EDU_PDF_FONT / EDU_PDF_FONT_BOLD, else Arial / DejaVu Sans.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from app.edu.quiz.schemas import QuizSet


def _fonts() -> Tuple[Path, Path]:
    env = os.getenv("EDU_PDF_FONT")
    if env and Path(env).is_file():
        bold = os.getenv("EDU_PDF_FONT_BOLD")
        return Path(env), Path(bold) if bold and Path(bold).is_file() else Path(env)
    candidates = [
        (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", "arial.ttf", "arialbd.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/usr/share/fonts/dejavu-sans-fonts"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/System/Library/Fonts/Supplemental"), "Arial.ttf", "Arial Bold.ttf"),
    ]
    for d, regular, bold in candidates:
        if (d / regular).is_file():
            return d / regular, (d / bold if (d / bold).is_file() else d / regular)
    raise RuntimeError("Không tìm thấy font Unicode (Arial / DejaVu Sans). Đặt EDU_PDF_FONT=đường_dẫn.ttf")


def render(qs: QuizSet, answers: bool = False) -> bytes:
    from fpdf import FPDF

    regular, bold = _fonts()
    pdf = FPDF()
    pdf.add_font("U", fname=str(regular))
    pdf.add_font("U", style="B", fname=str(bold))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def line(text: str, size: int = 11, b: bool = False, gap: float = 0):
        pdf.set_font("U", style="B" if b else "", size=size)
        pdf.multi_cell(0, 6.5, text=str(text), new_x="LMARGIN", new_y="NEXT")
        if gap:
            pdf.ln(gap)

    questions = [q for q in qs.questions if q.decision in ("chap_nhan", "da_sua")] or \
                [q for q in qs.questions if q.decision != "tu_choi_cau"]
    line(qs.title + (" — Đáp án" if answers else ""), 16, True)
    line(f"{len(questions)} câu", 9, gap=2)
    if not answers:
        line("Họ và tên: ................................................   Lớp: ..............", 10, gap=4)

    for n, q in enumerate(questions, 1):
        tag = " · ".join(x for x in (q.bloom, {"tinh_huong": "Tình huống", "nhieu_buoc": "Nhiều bước",
                                                "doc_bang": "Đọc bảng", "doc_hinh": "Đọc hình"}.get(q.depth or "")) if x)
        line(f"Câu {n}." + (f"  ({tag})" if tag else ""), 11, True)
        line(q.stem)
        if not answers:
            for o in q.options:
                line(f"   {o.key}. {o.text}")
            if q.type == "short_answer":
                line("   Trả lời: ...........................................................................")
        else:
            if q.type == "mcq":
                line(f"Đáp án: {q.correct_key or '(chưa có)'}", 11, True)
                for o in q.options:
                    if o.key != q.correct_key and o.misconception:
                        line(f"   {o.key} sai vì: {o.misconception}", 10)
            elif q.type == "true_false":
                line("Đáp án: " + ", ".join(f"{o.key}) {'Đ' if o.is_correct else 'S'}" for o in q.options), 11, True)
            else:
                line(f"Đáp án mẫu: {q.answer_text or ''}", 11, True)
            if q.explanation:
                line(f"Giải thích: {q.explanation}", 10)
            src = ", ".join(q.source_chunk_ids or ([q.source.chunk_id] if q.source.chunk_id else []))
            if src or q.source.heading_path:
                line(f"Nguồn: {src}" + (f" ({' > '.join(q.source.heading_path)})" if q.source.heading_path else ""), 9)
            if q.verdict:
                line(f"Kiểm nguồn: {q.verdict.get('nhan')}", 9)
        pdf.ln(3)
    return bytes(pdf.output())
