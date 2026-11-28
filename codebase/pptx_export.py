"""Xuất bộ slide ra PowerPoint (.pptx) bằng python-pptx: cùng bảng màu và bố cục với bản HTML (deck.py).
Lời thuyết trình nằm trong ghi chú của từng slide; ảnh trích từ tài liệu được đặt vừa khung, giữ tỉ lệ."""
import os
from pathlib import Path

try:
    from . import deck
except ImportError:
    import deck


def _rgb(hexcolor):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(hexcolor.lstrip("#").upper())


def export_pptx(slides: list[dict], out_dir: str, title: str = "Slide", options: dict | None = None) -> str:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Emu, Inches, Pt

    options = options or {}
    _, t = deck.theme_of(options)
    image_dir = options.get("image_dir")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, H = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]
    FONT = "Calibri"

    def rect(sl, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, line=None, radius=None):
        s = sl.shapes.add_shape(shape, x, y, w, h)
        s.fill.solid()
        s.fill.fore_color.rgb = _rgb(fill)
        if line:
            s.line.color.rgb = _rgb(line)
            s.line.width = Pt(1)
        else:
            s.line.fill.background()
        if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            s.adjustments[0] = radius
        s.shadow.inherit = False
        return s

    def text(sl, x, y, w, h, value, size, color, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=None):
        box = sl.shapes.add_textbox(x, y, w, h)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        paras = value if isinstance(value, list) else [value]
        for i, v in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if spacing:
                p.space_after = Pt(spacing)
            r = p.add_run()
            r.text = str(v)
            r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
            r.font.color.rgb = _rgb(color)
        return box

    def background(sl, color):
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = _rgb(color)

    # ---- bìa
    sl = prs.slides.add_slide(blank)
    background(sl, t["cover1"])
    rect(sl, W - Inches(5), Inches(-1.5), Inches(7), Inches(7), t["cover2"], MSO_SHAPE.OVAL)
    rect(sl, Inches(0.9), Inches(2.3), Inches(1.1), Inches(0.09), t["accent2"])
    text(sl, Inches(0.9), Inches(1.7), Inches(4), Inches(0.4), "BÀI GIẢNG", 16, t["accent2"], True)
    text(sl, Inches(0.9), Inches(2.55), Inches(10), Inches(2.2), title, 44, t["cover_ink"], True)
    text(sl, Inches(0.9), Inches(5.0), Inches(9), Inches(1), options.get("phu_de") or "%d nội dung chính" % len(slides), 20, t["cover_ink"])

    for index, s in enumerate(slides, 1):
        sl = prs.slides.add_slide(blank)
        background(sl, t["bg"])
        rect(sl, Inches(0.7), Inches(0.62), Inches(0.7), Inches(0.07), t["accent"])
        text(sl, Inches(1.55), Inches(0.5), Inches(8), Inches(0.3), str(s.get("tu_khoa") or "Nội dung %d" % index).upper(), 13, t["accent"], True)
        text(sl, W - Inches(1.7), Inches(0.5), Inches(1), Inches(0.3), "%02d" % index, 13, t["muted"], True, PP_ALIGN.RIGHT)
        text(sl, Inches(0.7), Inches(0.95), W - Inches(1.4), Inches(1.2), s.get("tieu_de", ""), 36, t["ink"], True)
        pts = [str(p) for p in (s.get("y_chinh") or []) if str(p).strip()]
        imgs = deck.image_paths(s, image_dir)
        body_top, body_h = Inches(2.35), Inches(4.2)
        if imgs:
            left = index % 2 == 0
            tx = Inches(6.7) if left else Inches(0.7)
            ix = Inches(0.7) if left else Inches(7.3)
            tw, iw = Inches(5.9), Inches(5.3)
            for i, p in enumerate(pts):
                y = body_top + Inches(1.3) * i
                rect(sl, tx, y, Inches(0.5), Inches(0.5), t["primary"], MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
                text(sl, tx, y, Inches(0.5), Inches(0.5), str(i + 1), 15, t["chip_ink"], True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
                text(sl, tx + Inches(0.7), y, tw - Inches(0.7), Inches(1.2), p, 20, t["ink"])
            rect(sl, ix, body_top, iw, body_h, t["surface"], MSO_SHAPE.ROUNDED_RECTANGLE, line=t["line"], radius=0.04)
            try:
                from PIL import Image
                with Image.open(imgs[0]) as im:
                    ar = im.width / im.height
                pw, ph = iw - Inches(0.3), body_h - Inches(0.3)
                w, h = (pw, int(pw / ar)) if pw / ar <= ph else (int(ph * ar), ph)
                sl.shapes.add_picture(imgs[0], int(ix + (iw - w) / 2), int(body_top + (body_h - h) / 2), width=int(w), height=int(h))
            except Exception:
                pass
            text(sl, ix, body_top + body_h + Inches(0.08), iw, Inches(0.3), "Hình trích từ tài liệu · %s" % s.get("segment_id", ""), 11, t["muted"])
        elif len(pts) >= 3:
            cw = (W - Inches(1.4) - Inches(0.5)) / 3
            for i, p in enumerate(pts[:3]):
                x = Inches(0.7) + (cw + Inches(0.25)) * i
                rect(sl, x, body_top, int(cw), Inches(3.9), t["surface"], MSO_SHAPE.ROUNDED_RECTANGLE, line=t["line"], radius=0.05)
                rect(sl, x, body_top, int(cw), Inches(0.09), t["accent"])
                text(sl, x + Inches(0.3), body_top + Inches(0.4), Inches(1.5), Inches(0.8), "%02d" % (i + 1), 32, t["accent"], True)
                text(sl, x + Inches(0.3), body_top + Inches(1.3), int(cw) - Inches(0.6), Inches(2.4), p, 19, t["ink"])
        else:
            kw = rect(sl, Inches(0.7), body_top, Inches(4.6), Inches(3.9), t["cover1"], MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
            text(sl, Inches(0.95), body_top, Inches(4.1), Inches(3.9), s.get("tu_khoa") or s.get("tieu_de", ""), 30, t["cover_ink"], True,
                 PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
            for i, p in enumerate(pts):
                y = body_top + Inches(1.3) * i
                rect(sl, Inches(5.8), y, Inches(0.5), Inches(0.5), t["primary"], MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
                text(sl, Inches(5.8), y, Inches(0.5), Inches(0.5), str(i + 1), 15, t["chip_ink"], True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
                text(sl, Inches(6.5), y, Inches(6.1), Inches(1.2), p, 20, t["ink"])
        text(sl, Inches(0.7), H - Inches(0.55), Inches(8), Inches(0.3), "Nguồn %s" % s.get("segment_id", ""), 11, t["muted"])
        text(sl, W - Inches(1.7), H - Inches(0.55), Inches(1), Inches(0.3), "%d / %d" % (index + 1, len(slides) + 2), 11, t["muted"], False, PP_ALIGN.RIGHT)
        sl.notes_slide.notes_text_frame.text = str(s.get("loi_thuyet_trinh", ""))

    # ---- kết
    sl = prs.slides.add_slide(blank)
    background(sl, t["cover1"])
    text(sl, Inches(0.9), Inches(0.9), Inches(8), Inches(0.9), "Những điều cần nhớ", 40, t["cover_ink"], True)
    text(sl, Inches(0.9), Inches(2.2), Inches(7.5), Inches(4.5), ["%02d   %s" % (i + 1, s.get("tieu_de", "")) for i, s in enumerate(slides[:7])],
         20, t["cover_ink"], spacing=10)
    uniq = []
    for s in slides:
        if s.get("segment_id") and s["segment_id"] not in uniq:
            uniq.append(s["segment_id"])
    text(sl, Inches(9), Inches(2.2), Inches(3.8), Inches(0.4), "NGUỒN TÀI LIỆU", 13, t["accent2"], True)
    text(sl, Inches(9), Inches(2.7), Inches(3.8), Inches(3), ", ".join(uniq), 15, t["cover_ink"])

    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / "slides.pptx"
    prs.save(str(target))
    return str(target)
