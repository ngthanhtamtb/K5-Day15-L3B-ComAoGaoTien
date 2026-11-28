"""Export Vietnamese quizzes, standalone slide decks, and narrated audio."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from html import escape
import os
from pathlib import Path
from urllib.parse import quote


ALLOWED_VOICES = {"vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"}


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

    def document():
        pdf = FPDF()
        pdf.add_font("Unicode", fname=str(regular))
        pdf.add_font("Unicode", style="B", fname=str(bold))
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        return pdf

    def paragraph(pdf, text, heading=False):
        pdf.set_font("Unicode", style="B" if heading else "", size=14 if heading else 11)
        pdf.multi_cell(0, 7, text=str(text), new_x="LMARGIN", new_y="NEXT")

    exam, answers = document(), document()
    paragraph(exam, title, True)
    paragraph(answers, f"{title} — Đáp án", True)
    for number, question in enumerate(quiz, 1):
        paragraph(exam, f"Câu {number}. {question['de']}", True)
        for letter in "ABCD":
            paragraph(exam, f"{letter}. {question[letter]}")
        exam.ln(3)
        paragraph(answers, f"Câu {number}. Đáp án: {question['dap_an']}", True)
        paragraph(answers, f"Giải thích: {question['giai_thich']}")
        paragraph(answers, f"Nguồn: {question['segment_id']}")
        answers.ln(3)
    paths = {"exam_pdf": str(directory / "quiz_exam.pdf"), "answer_pdf": str(directory / "quiz_answers.pdf")}
    exam.output(paths["exam_pdf"])
    answers.output(paths["answer_pdf"])
    return paths


def render_slides(slides: list[dict], out_dir: str, title: str = "Slide", audio: dict | None = None,
                  options: dict | None = None) -> str:
    """Write an escaped HTML deck; audio files remain relative external assets.

    options (tuỳ chọn, giá trị lạ bị bỏ qua): mau "AI20K chuẩn" | "Tối giản", ty_le "16:9" | "4:3",
    ghi_chu bool (hiện lời thuyết trình dưới mỗi slide, mặc định True). Không truyền → hành vi cũ."""
    options = options or {}
    minimal = options.get("mau") == "Tối giản"
    ratio = {"16:9": "16/9", "4:3": "4/3"}.get(options.get("ty_le"))
    show_notes = options.get("ghi_chu", True) is not False
    extra_css = (("body{background:#fff}section{border:1px solid #ccc;border-radius:0;padding:1.2rem}" if minimal else "")
                 + (f"section{{aspect-ratio:{ratio};overflow:auto}}" if ratio else ""))
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe = lambda value: escape(str(value), quote=True)
    sections = []
    for index, slide in enumerate(slides, 1):
        player = ""
        if audio and index in audio:
            relative = os.path.relpath(Path(audio[index]).resolve(), directory.resolve())
            source = quote(Path(relative).as_posix(), safe="/.")
            player = f'<audio controls preload="none" src="{safe(source)}"></audio>'
        points = "".join(f"<li>{safe(point)}</li>" for point in slide["y_chinh"])
        hidden = "" if index == 1 else " hidden"
        sections.append(
            f'<section class="slide"{hidden}><h2>{safe(slide["tieu_de"])}</h2>'
            f'<ul>{points}</ul><p>Nguồn: {safe(slide["segment_id"])}</p>'
            + (f'<details><summary>Lời thuyết trình</summary><p>{safe(slide["loi_thuyet_trinh"])}</p></details>'
               if show_notes else "")
            + f'{player}</section>'
        )
    content = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + safe(title) + """</title><style>
body{font-family:Arial,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;background:#f6f8fc;color:#17243a}
section{background:white;padding:2rem;border-radius:12px}li{margin:1rem 0}
p,li,h1,h2{white-space:pre-wrap;overflow-wrap:anywhere}button{padding:.7rem 1rem;margin:1rem .3rem}
audio{display:block;margin-top:1rem;max-width:100%}summary{cursor:pointer}[hidden]{display:none}
""" + extra_css + """
</style></head><body><h1>""" + safe(title) + "</h1>" + "".join(sections) + """
<nav aria-label="Điều hướng"><button id="previous" type="button">Trước</button>
<span id="position" aria-live="polite"></span><button id="next" type="button">Sau</button></nav>
<script>
const slides = Array.from(document.querySelectorAll('.slide'));
let current = 0;
function show(index) {
  current = Math.max(0, Math.min(index, slides.length - 1));
  slides.forEach((slide, i) => {
    slide.hidden = i !== current;
    if (slide.hidden) slide.querySelectorAll('audio').forEach(audio => audio.pause());
  });
  document.getElementById('position').textContent = slides.length ? `${current + 1} / ${slides.length}` : '0 / 0';
  document.getElementById('previous').disabled = !slides.length || current === 0;
  document.getElementById('next').disabled = !slides.length || current === slides.length - 1;
}
document.getElementById('previous').addEventListener('click', () => show(current - 1));
document.getElementById('next').addEventListener('click', () => show(current + 1));
document.addEventListener('keydown', event => {
  if (event.target.closest('audio, input, textarea, select, [contenteditable]')) return;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault(); show(current + (event.key === 'ArrowRight' ? 1 : -1));
  }
});
show(0);
</script></body></html>"""
    path = directory / "slides.html"
    path.write_text(content, encoding="utf-8")
    return str(path)


def synthesize_voice(slide_id: int, text: str, out_dir: str, voice: str = "vi-VN-HoaiMyNeural") -> str:
    """Generate MP3 speech, including when called from a running event loop."""
    if voice not in ALLOWED_VOICES:
        raise ValueError("Giọng không được phép. Chỉ hỗ trợ vi-VN-HoaiMyNeural và vi-VN-NamMinhNeural.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text không được rỗng.")
    if not isinstance(slide_id, int) or isinstance(slide_id, bool) or slide_id < 1:
        raise ValueError("slide_id phải là số nguyên từ 1.")
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"slide_{slide_id}.mp3"

    async def generate():
        import edge_tts

        await edge_tts.Communicate(text, voice).save(str(path))

    def run():
        asyncio.run(generate())

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
