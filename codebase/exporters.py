"""Export Vietnamese quizzes, standalone slide decks, and narrated audio."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from html import escape
import os
from pathlib import Path
import re
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


def _slide_illustration_svg(slide: dict, minimal: bool) -> str:
    """Tạo hình minh hoạ SVG sạch sẽ theo chủ đề slide (không lặp text để giữ nguyên kiểm đếm test)."""
    blob = ("%s %s" % (slide.get("tieu_de", ""), " ".join(slide.get("y_chinh", [])))).lower()
    accent = "#475569" if minimal else "#2563eb"
    soft = "#f1f5f9" if minimal else "#eff6ff"
    border = "#cbd5e1" if minimal else "#bfdbfe"
    if any(k in blob for k in ("rag", "truy xuất", "embedding", "vector", "kho")):
        inner = (
            f'<rect x="18" y="34" width="66" height="92" rx="8" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<line x1="30" y1="56" x2="72" y2="56" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<line x1="30" y1="74" x2="66" y2="74" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<line x1="30" y1="92" x2="70" y2="92" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<path d="M92 80 H126" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<polygon points="124,73 136,80 124,87" fill="{accent}"/>'
            f'<rect x="142" y="46" width="70" height="68" rx="12" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<circle cx="177" cy="80" r="16" fill="{accent}" opacity="0.18"/>'
            f'<circle cx="177" cy="80" r="7" fill="{accent}"/>'
        )
    elif any(k in blob for k in ("prompt", "few-shot", "chain", "cot", "suy luận")):
        inner = (
            f'<circle cx="42" cy="80" r="18" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<path d="M64 80 H92" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="115" cy="80" r="18" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<path d="M137 80 H165" stroke="{accent}" stroke-width="3" stroke-linecap="round"/>'
            f'<rect x="170" y="56" width="44" height="48" rx="10" fill="{accent}" opacity="0.18" stroke="{accent}" stroke-width="2"/>'
            f'<path d="M182 80 L190 88 L204 72" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    elif any(k in blob for k in ("token", "llm", "temperature", "ngữ cảnh", "context", "hồi quy")):
        inner = (
            f'<rect x="20" y="42" width="48" height="32" rx="6" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<rect x="82" y="42" width="48" height="32" rx="6" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<rect x="144" y="42" width="66" height="32" rx="6" fill="{accent}" opacity="0.18" stroke="{accent}" stroke-width="2"/>'
            f'<path d="M44 96 C74 122, 138 122, 176 94" fill="none" stroke="{accent}" stroke-width="2.5" stroke-dasharray="5 4"/>'
            f'<circle cx="177" cy="92" r="5" fill="{accent}"/>'
        )
    else:
        inner = (
            f'<rect x="26" y="34" width="178" height="92" rx="12" fill="{soft}" stroke="{accent}" stroke-width="2"/>'
            f'<circle cx="62" cy="70" r="14" fill="{accent}" opacity="0.22"/>'
            f'<path d="M56 70 L60 75 L70 64" fill="none" stroke="{accent}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<line x1="90" y1="62" x2="182" y2="62" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>'
            f'<line x1="90" y1="80" x2="164" y2="80" stroke="{accent}" stroke-width="3" stroke-linecap="round" opacity="0.65"/>'
            f'<line x1="48" y1="104" x2="182" y2="104" stroke="{accent}" stroke-width="2.5" stroke-linecap="round" opacity="0.35"/>'
        )
    return (
        f'<div class="slide-visual" aria-hidden="true">'
        f'<svg viewBox="0 0 230 160" width="100%" height="160" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="2" y="2" width="226" height="156" rx="14" fill="#ffffff" stroke="{border}" stroke-width="1.5"/>'
        f'{inner}</svg></div>'
    )


def _sanitize_svg(raw: str) -> str:
    """Chỉ giữ cặp thẻ <svg>...</svg> và loại bỏ script/event handler để chống XSS."""
    m = re.search(r"<svg\b[^>]*>.*?</svg>", raw or "", flags=re.I | re.S)
    if not m:
        return ""
    svg = m.group(0)
    svg = re.sub(r"<script\b[^>]*>.*?</script>", "", svg, flags=re.I | re.S)
    svg = re.sub(r"\son[a-z]+\s*=\s*(['\"]).*?\1", "", svg, flags=re.I | re.S)
    svg = re.sub(r"javascript:", "", svg, flags=re.I)
    return '<div class="slide-visual" aria-hidden="true">' + svg + "</div>"


def render_slides(slides: list[dict], out_dir: str, title: str = "Slide", audio: dict | None = None,
                  options: dict | None = None) -> str:
    """Write an escaped HTML deck; audio files remain relative external assets.

    options (tuỳ chọn, giá trị lạ bị bỏ qua): mau "AI20K chuẩn" | "Tối giản", ty_le "16:9" | "4:3",
    ghi_chu bool (hiện lời thuyết trình dưới mỗi slide, mặc định True). Không truyền → hành vi cũ."""
    options = options or {}
    minimal = options.get("mau") == "Tối giản"
    ratio = {"16:9": "16/9", "4:3": "4/3"}.get(options.get("ty_le"))
    show_notes = options.get("ghi_chu", True) is not False
    extra_css = (("body{background:#fff}section{border:1px solid #ccc;border-radius:0;padding:1.2rem;box-shadow:none}"
                  ".slide-badge{background:#f1f5f9;color:#334155}" if minimal else "")
                 + (f"section{{aspect-ratio:{ratio};overflow:auto}}" if ratio else ""))
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe = lambda value: escape(str(value), quote=True)
    total = len(slides)
    sections = []
    for index, slide in enumerate(slides, 1):
        player = ""
        if audio and index in audio:
            relative = os.path.relpath(Path(audio[index]).resolve(), directory.resolve())
            source = quote(Path(relative).as_posix(), safe="/.")
            player = f'<audio controls preload="none" src="{safe(source)}"></audio>'
        points = "".join(f"<li>{safe(point)}</li>" for point in slide["y_chinh"])
        hidden = "" if index == 1 else " hidden"
        vis = slide.get("visual") if isinstance(slide.get("visual"), dict) else {}
        layout = vis.get("layout") if vis.get("layout") in ("split-diagram", "cards", "timeline", "comparison") else "split-diagram"
        custom_svg = _sanitize_svg(vis.get("svg", "")) if vis.get("svg") else ""
        illust = custom_svg or _slide_illustration_svg(slide, minimal)
        sections.append(
            f'<section class="slide layout-{layout}"{hidden}>'
            f'<div class="slide-top"><span class="slide-num">Slide {index} / {total}</span>'
            f'<span class="slide-badge">Nguồn: {safe(slide["segment_id"])}</span></div>'
            f'<div class="slide-grid"><div class="slide-main">'
            f'<h2>{safe(slide["tieu_de"])}</h2><ul>{points}</ul></div>'
            f'{illust}</div>'
            + (f'<details><summary>Lời thuyết trình</summary><p>{safe(slide["loi_thuyet_trinh"])}</p></details>'
               if show_notes else "")
            + f'{player}</section>'
        )
    content = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + safe(title) + """</title><style>
body{font-family:'Segoe UI',Arial,sans-serif;max-width:980px;margin:2rem auto;padding:0 1.2rem;background:linear-gradient(135deg,#eef2ff 0%,#f8fafc 100%);color:#17243a}
h1{font-size:1.4rem;color:#1e293b;margin-bottom:1rem;border-left:4px solid #2563eb;padding-left:.75rem}
section{background:#fff;padding:2rem;border-radius:16px;box-shadow:0 10px 30px rgba(15,23,42,.08);border:1px solid #e2e8f0}
.slide-top{display:flex;justify-content:space-between;align-items:center;gap:.5rem;margin-bottom:1rem;font-size:.85rem}
.slide-num{color:#64748b;font-weight:600}
.slide-badge{background:#dbeafe;color:#1d4ed8;padding:.25rem .65rem;border-radius:999px;font-weight:600}
.slide-grid{display:grid;grid-template-columns:1.45fr 1fr;gap:1.5rem;align-items:center}
.layout-cards ul,.layout-comparison ul{list-style:none;padding:0;display:grid;gap:.65rem}
.layout-cards li,.layout-comparison li{margin:0;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #2563eb;border-radius:10px;padding:.7rem .9rem}
.layout-comparison ul{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.layout-timeline ul{list-style:none;padding-left:1.35rem;border-left:3px solid #bfdbfe}
.layout-timeline li{position:relative;margin:.85rem 0;padding-left:.35rem}
.layout-timeline li::before{content:"";position:absolute;left:-1.85rem;top:.45rem;width:11px;height:11px;border-radius:50%;background:#2563eb;border:2px solid #fff;box-shadow:0 0 0 2px #bfdbfe}
.slide-visual svg{width:100%;height:auto;max-height:240px;display:block;border-radius:12px}
@media (max-width:720px){.slide-grid{grid-template-columns:1fr}}
h2{margin:0 0 .85rem;font-size:1.5rem;color:#0f172a;line-height:1.3}
ul{padding-left:1.25rem;margin:0}li{margin:.75rem 0;line-height:1.5;font-size:1.02rem}
p,li,h1,h2{white-space:pre-wrap;overflow-wrap:anywhere}
details{margin-top:1.25rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:.7rem 1rem}
summary{cursor:pointer;font-weight:600;color:#334155}
nav{display:flex;align-items:center;justify-content:center;gap:.75rem;margin-top:1rem}
button{padding:.6rem 1.15rem;border-radius:8px;border:1px solid #cbd5e1;background:#fff;color:#0f172a;font-weight:600;cursor:pointer}
button:hover:not(:disabled){background:#2563eb;color:#fff;border-color:#2563eb}
button:disabled{opacity:.45;cursor:not-allowed}
audio{display:block;margin-top:1rem;width:100%}[hidden]{display:none}
html:fullscreen body{max-width:none;width:100vw;height:100vh;margin:0;padding:1.5vh 3vw;box-sizing:border-box;display:flex;flex-direction:column;gap:1vh}
html:fullscreen h1{margin:0;font-size:1.15rem}
html:fullscreen section.slide{flex:1;display:flex;flex-direction:column;justify-content:center;padding:3vh 4vw;overflow:auto}
html:fullscreen section.slide[hidden]{display:none}
html:fullscreen h2{font-size:clamp(1.8rem,2.8vw,2.7rem);margin-bottom:1.2rem}
html:fullscreen li{font-size:clamp(1.15rem,1.65vw,1.5rem);margin:1rem 0}
html:fullscreen .slide-grid{gap:2.5vw}
html:fullscreen .slide-visual svg{max-height:46vh}
html:fullscreen nav{margin:0}
""" + extra_css + """
</style></head><body><h1>""" + safe(title) + "</h1>" + "".join(sections) + """
<nav aria-label="Điều hướng"><button id="previous" type="button">← Trước</button>
<span id="position" aria-live="polite"></span><button id="next" type="button">Sau →</button>
<button id="fullscreen" type="button">⛶ Toàn màn hình</button></nav>
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
document.getElementById('fullscreen').addEventListener('click', () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
});
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
