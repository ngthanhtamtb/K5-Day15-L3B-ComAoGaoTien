"""Build small PDF / PPTX files in memory (no binary fixtures in the repo)."""
import io


def png_bytes(w=120, h=80, color=(30, 120, 200)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def make_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    for n in range(1, 4):
        page = doc.new_page(width=595, height=842)
        page.insert_text((40, 30), "Khoá AI20K - tài liệu nội bộ", fontsize=8)          # header (repeats)
        page.insert_text((290, 825), str(n), fontsize=8)                                  # page number
        if n == 1:
            page.insert_text((40, 90), "Buoi 7: Truy xuat RAG", fontsize=22)
            page.insert_text((40, 130), "RAG truy xuat cac doan tai lieu lien quan roi dua vao prompt.", fontsize=11)
            page.insert_text((40, 148), "Chunk 500 token, chong lan 50 token, top-k = 5.", fontsize=11)
            # ruled 3x2 table
            x0, y0, cw, rh = 40, 180, 160, 22
            rows = [["Tham so", "Gia tri"], ["chunk", "500"], ["top-k", "5"]]
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    rect = fitz.Rect(x0 + c * cw, y0 + r * rh, x0 + (c + 1) * cw, y0 + (r + 1) * rh)
                    page.draw_rect(rect, color=(0, 0, 0), width=0.8)
                    page.insert_text((rect.x0 + 4, rect.y1 - 6), val, fontsize=10)
            page.insert_image(fitz.Rect(40, 280, 200, 387), stream=png_bytes())
            page.insert_text((40, 400), "Hinh 1. So do luong RAG", fontsize=9)
        else:
            page.insert_text((40, 90), f"Muc {n}: Embedding", fontsize=16)
            page.insert_text((40, 130), "Embedding bieu dien doan van thanh vector so; do gan bang cosine.", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def make_pptx() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Temperature"
    body = s.placeholders[1].text_frame
    body.text = "Temperature thap: phan bo nhon hon"
    p = body.add_paragraph(); p.text = "Temperature cao: da dang hon"; p.level = 1
    s.notes_slide.notes_text_frame.text = "Nhac hoc vien: temperature cao khong lam on dinh hon."
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Tham so lab"
    tbl = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    tbl.cell(0, 0).text, tbl.cell(0, 1).text, tbl.cell(1, 0).text, tbl.cell(1, 1).text = "chunk", "500", "top-k", "5"
    s2.shapes.add_picture(io.BytesIO(png_bytes()), Inches(6), Inches(2), Inches(2), Inches(1.3))
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
