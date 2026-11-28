"""Export Vietnamese quizzes, standalone slide decks, and narrated audio."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from html import escape
import os
from pathlib import Path
import re
import time

try:
    from . import deck
except ImportError:          # chạy với codebase/ nằm trong sys.path (API, run.py)
    import deck


ALLOWED_VOICES = {"vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"}
ALLOWED_RATES = {"-20%", "-15%", "-10%", "+0%", "+10%", "+15%", "+20%", "+25%"}


def _clean_tts_text(text: str) -> str:
    """Làm sạch mã đoạn trích dẫn [D01-S02] hoặc ký hiệu thừa trước khi đọc thành tiếng."""
    cleaned = re.sub(r"\[\s*(?:nguồn\s*:\s*)?D\d{2}-[SQ]\d{2,3}[^\]]*\]", "", text)
    cleaned = re.sub(r"[*_`#>]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned or text.strip()


def _find_fonts() -> tuple[Path, Path]:
    candidates = [
        (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", "arial.ttf", "arialbd.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/usr/share/fonts/dejavu-sans-fonts"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/usr/local/share/fonts"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path.home() / ".local/share/fonts", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        (Path("/System/Library/Fonts/Supplemental"), "Arial.ttf", "Arial Bold.ttf"),
        (Path("/Library/Fonts"), "Arial.ttf", "Arial Bold.ttf"),
    ]
    for directory, regular, bold in candidates:
        if (directory / regular).is_file():
            return directory / regular, (directory / bold if (directory / bold).is_file() else directory / regular)
    raise RuntimeError("Không tìm thấy font Unicode TTF. Hãy cài Arial hoặc DejaVu Sans để xuất PDF tiếng Việt.")


def export_quiz_pdf(quiz: list[dict], out_dir: str, title: str = "Quiz") -> dict:
    """Write separate question and answer PDFs using an embedded Unicode font."""
    from fpdf import FPDF

    regular, bold = _find_fonts()
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    NAVY, TEAL, INK, MUTED, LINE = (18, 53, 91), (14, 159, 154), (20, 30, 50), (90, 104, 124), (213, 221, 234)

    def document(heading, sub):
        pdf = FPDF()
        pdf.add_font("Unicode", fname=str(regular))
        pdf.add_font("Unicode", style="B", fname=str(bold))
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.set_margins(18, 16, 18)
        pdf.add_page()
        pdf.set_fill_color(*NAVY)
        pdf.rect(0, 0, 210, 34, "F")
        pdf.set_fill_color(*TEAL)
        pdf.rect(0, 34, 210, 2.2, "F")
        pdf.set_xy(18, 9)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Unicode", style="B", size=17)
        pdf.multi_cell(174, 8, text=str(heading), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(18)
        pdf.set_font("Unicode", size=10)
        pdf.set_text_color(210, 225, 245)
        pdf.cell(174, 6, text=sub, new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(44)
        pdf.set_text_color(*INK)
        return pdf

    def paragraph(pdf, text, heading=False, indent=0.0, color=INK, size=None):
        pdf.set_x(18 + indent)
        pdf.set_text_color(*color)
        pdf.set_font("Unicode", style="B" if heading else "", size=size or (12 if heading else 11))
        pdf.multi_cell(174 - indent, 6.4, text=str(text), new_x="LMARGIN", new_y="NEXT")

    def rule(pdf):
        pdf.set_draw_color(*LINE)
        pdf.line(18, pdf.get_y() + 1.5, 192, pdf.get_y() + 1.5)
        pdf.ln(5)

    exam = document(title, "Họ và tên: ................................   Lớp: ..........   Ngày: ..../..../........")
    answers = document(f"{title} — Đáp án", "Đáp án, giải thích và đoạn nguồn trích dẫn cho từng câu")
    for number, question in enumerate(quiz, 1):
        paragraph(exam, f"Câu {number}. {question['de']}", True)
        exam.ln(1)
        for letter in "ABCD":
            paragraph(exam, f"{letter}. {question[letter]}", indent=6)
        rule(exam)
        paragraph(answers, f"Câu {number}. Đáp án: {question['dap_an']}", True, color=NAVY)
        paragraph(answers, f"Giải thích: {question['giai_thich']}", indent=4)
        paragraph(answers, f"Nguồn: {question['segment_id']}", indent=4, color=MUTED, size=9.5)
        rule(answers)
    paths = {"exam_pdf": str(directory / "quiz_exam.pdf"), "answer_pdf": str(directory / "quiz_answers.pdf")}
    exam.output(paths["exam_pdf"])
    answers.output(paths["answer_pdf"])
    return paths


def render_slides(slides: list[dict], out_dir: str, title: str = "Slide", audio: dict | None = None,
                  options: dict | None = None) -> str:
    """Ghi bộ slide HTML (xem deck.py). options: mau, image_dir, nguon, phu_de, meta. Giá trị lạ bị bỏ qua."""
    return deck.render_deck(slides, out_dir, title, audio, options)


def synthesize_voice(slide_id: int, text: str, out_dir: str, voice: str = "vi-VN-HoaiMyNeural",
                     rate: str = "+0%") -> str:
    """Generate MP3 speech, including when called from a running event loop."""
    if voice not in ALLOWED_VOICES:
        raise ValueError("Giọng không được phép. Chỉ hỗ trợ vi-VN-HoaiMyNeural và vi-VN-NamMinhNeural.")
    if rate not in ALLOWED_RATES:
        rate = "+0%"
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text không được rỗng.")
    if not isinstance(slide_id, int) or isinstance(slide_id, bool) or slide_id < 1:
        raise ValueError("slide_id phải là số nguyên từ 1.")
    cleaned = _clean_tts_text(text)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"slide_{slide_id}.mp3"

    async def generate():
        import edge_tts

        comm = edge_tts.Communicate(cleaned, voice) if rate == "+0%" else edge_tts.Communicate(cleaned, voice, rate=rate)
        await comm.save(str(path))

    def run():
        last = None
        for attempt in range(4):          # edge-tts thỉnh thoảng trả "No audio was received": thử lại với độ trễ tăng dần
            try:
                asyncio.run(generate())
                if path.is_file() and path.stat().st_size > 0:
                    return
                last = RuntimeError("file MP3 rỗng")
            except Exception as exc:
                last = exc
            time.sleep(1.2 * (attempt + 1))
        raise last

    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            run()
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(run).result()
    except Exception as exc:
        raise RuntimeError(f"Không thể tổng hợp giọng nói (mạng/dịch vụ edge-tts hoặc ghi MP3): {exc}") from exc
    return str(path)
